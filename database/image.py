from dataclasses import dataclass
from typing import Optional
from environs import Env
import os
import logging
from PIL import Image
from image.vectorize import DifferenceHash


logger = logging.getLogger(__name__)


@dataclass
class ImageRecord:
    userId: int  # 0 if image uploaded from local source
    userName: str  # Optional user name
    imageName: str
    uploadDate: str  # Формат даты: 'YYYY-MM-DD HH:MM:SS'
    imageHash: str
    imageType: str | None  # Holds type of image contenent, e.g., 'face', 'equip', etc.
    imageLocation: str | None  # Holds location of image, e.g., 'local', 's3', etc.
    unix_date: float # Unix timestamp
    im_predicted_class: str
    chat_id: str
    message_id: int


def exract_date_from_filename(filename: str) -> str:
    date_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[0]
    time_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[1]
    
    return date_part + ' ' + time_part.split('-')[0] + ':' \
        + time_part.split('-')[1] + ':' + time_part.split('-')[2] \
        if len(time_part.split('-')) == 3 else date_part + ' ' + time_part


async def initialize_database(db_pool):
    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(query="""CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                user_name VARCHAR(100),
                user_lang VARCHAR(2) DEFAULT 'UZ');""")

            await cursor.execute(query="""CREATE TABLE IF NOT EXISTS images(
                user_id BIGINT,
                user_name VARCHAR(50),
                image_name VARCHAR(100),
                upload_date VARCHAR(30),
                image_hash VARCHAR(50),
                image_type VARCHAR(10),
                image_location VARCHAR(10),
                up_date FLOAT,
                im_predicted_class VARCHAR(10));""")

            await cursor.execute(query="""CREATE TABLE IF NOT EXISTS route(
                agent_id BIGINT,
                reg_name VARCHAR(50) NOT NULL,
                visit_day INT NOT NULL
            );""")

            await cursor.execute(query="""CREATE TABLE IF NOT EXISTS equip(
                agent_id BIGINT,
                cust_name VARCHAR(50) NOT NULL,
                equip_type VARCHAR(20) NOT NULL,
                visit_day INT NOT NULL
            );""")
    logger.info("Database initialized successfully")


async def append_image_record(db_pool, record: ImageRecord,
                              ImgHash=None, filePath=None) -> None:

    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            if ImgHash is not None:
                record.imageHash = ImgHash
            else:
                theImage = Image.open(filePath)
                img_hash = DifferenceHash(theImage)
                record.imageHash = str(img_hash)
            
            await cursor.execute(
                 """
                    INSERT INTO images (user_id,
                    user_name,
                    image_name,
                    upload_date,
                    image_hash,
                    image_type,
                    image_location,
                    up_date,
                    im_predicted_class,
                    chat_id, message_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        record.userId,
                        record.userName if hasattr(record, 'userName') else '',
                        record.imageName,
                        record.uploadDate,
                        record.imageHash,
                        record.imageType,
                        record.imageLocation,
                        record.unix_date,
                        record.im_predicted_class,
                        record.chat_id,
                        record.message_id 
                    ),
                )


async def create_database(db_pool):
    records = []
    env = Env()
    env.read_env()
    imagePath = env.str("IMAGE_PATH")
    list_dir = os.listdir(imagePath)
    for file_name in list_dir:
        image_path = os.path.join(imagePath, file_name)
        if os.path.isfile(image_path):
            theImage = Image.open(image_path)
            img_hash = DifferenceHash(theImage)
            imgRec = ImageRecord(
                userId=0,
                imageName=file_name,
                uploadDate=exract_date_from_filename(file_name),
                imageHash=str(img_hash),
                imageType=None,
                imageLocation='local'
            )
            records.append(imgRec)
    for rec in records:
        await append_image_record(db_pool, rec)
    logger.info(f'{len(records)} images appended to the database')


async def find_similar_images(db_pool, photo) -> ImageRecord | None:
    theImage = Image.open(photo)
    img_hash = DifferenceHash(theImage)
    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("""SELECT user_id,
                                 user_name,  
                                 image_name,  
                                 upload_date, 
                                 image_location,
                                 up_date,
                                 im_predicted_class,
                                 chat_id,
                                 message_id
                                 FROM images 
                                 WHERE image_hash = (%s)
                                 ORDER BY upload_date DESC;""", [str(img_hash)])
            record = await cursor.fetchone()
            if record:
                imgRec = ImageRecord(
                    userId=record[0],
                    userName=record[1],
                    imageName=record[2],
                    uploadDate=record[3],
                    imageHash="",
                    imageType="",
                    imageLocation=record[4],
                    unix_date=record[5], 
                    im_predicted_class=record[6], 
                    chat_id=record[7],
                    message_id=record[8]
                )
                return imgRec
        return None


async def insert_routes(db_pool, routes_data: list[tuple]) -> int:
    """
    Insert route data into the database (UPSERT - replace if exists).

    Args:
        db_pool: Database connection pool
        routes_data: List of tuples (agent_id, reg_name, visit_day)

    Returns:
        Number of rows inserted/updated

    Raises:
        Exception: If database operation fails
    """
    if not routes_data:
        raise ValueError("No route data to insert")

    try:
        async with db_pool.connection() as connection:
            async with connection.cursor() as cursor:
                # Clear route table before update
                await cursor.execute("""DELETE FROM route;""")
                
                for agent_id, reg_name, visit_day in routes_data:
                    await cursor.execute(
                        """INSERT INTO route (agent_id, reg_name, visit_day)
                           VALUES (%s, %s, %s);
                           """,
                        (agent_id, reg_name, visit_day)
                    )
        logger.info(f"Successfully inserted/updated {len(routes_data)} routes")
        return len(routes_data)
    except Exception as e:
        logger.error(f"Error inserting routes: {e}")
        raise


async def insert_equip(db_pool, equip_data: list[tuple]) -> int:
    """
    Insert equipment data into the database (DELETE then INSERT).

    Args:
        db_pool: Database connection pool
        equip_data: List of tuples (agent_id, cust_name, equip_type, visit_day)

    Returns:
        Number of rows inserted

    Raises:
        Exception: If database operation fails
    """
    if not equip_data:
        raise ValueError("No equipment data to insert")

    try:
        async with db_pool.connection() as connection:
            async with connection.cursor() as cursor:
                # Clear equip table before update
                await cursor.execute("""DELETE FROM equip;""")

                for agent_id, cust_name, equip_type, visit_day in equip_data:
                    await cursor.execute(
                        """INSERT INTO equip (agent_id, cust_name, equip_type, visit_day)
                           VALUES (%s, %s, %s, %s);
                           """,
                        (agent_id, cust_name, equip_type, visit_day)
                    )
        logger.info(f"Successfully inserted {len(equip_data)} equipment records")
        return len(equip_data)
    except Exception as e:
        logger.error(f"Error inserting equipment: {e}")
        raise


async def add_or_update_user(db_pool, user_id: int, user_name: str, user_lang: str = 'ru') -> None:
    """Add user if not exists in users table"""
    async with db_pool.connection() as conn:
        async with conn.cursor() as cursor:
            # Check if user already exists
            await cursor.execute(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            # If user doesn't exist, insert
            if not exists:
                await cursor.execute(
                    """INSERT INTO users (user_id, user_name, user_lang)
                       VALUES (%s, %s, %s)""",
                    (user_id, user_name, user_lang)
                )


async def get_user_language(db_pool, user_id: int) -> str:
    """Get user's preferred language, defaults to 'ru'"""
    async with db_pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT user_lang FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 'UZ'

