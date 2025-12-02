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
    imageName: str
    uploadDate: str  # Формат даты: 'YYYY-MM-DD HH:MM:SS'
    imageHash: str
    imageType: str | None  # Holds type of image contenent, e.g., 'face', 'equip', etc.
    imageLocation: str | None  # Holds location of image, e.g., 'local', 's3', etc.


def exract_date_from_filename(filename: str) -> str:
    date_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[0]
    time_part = filename[filename.find('@') + 1:filename.rfind('.')].split('_')[1]
    
    return date_part + ' ' + time_part.split('-')[0] + ':' \
        + time_part.split('-')[1] + ':' + time_part.split('-')[2] \
        if len(time_part.split('-')) == 3 else date_part + ' ' + time_part


async def append_image_record(db_pool, record: ImageRecord,
                              ImgHash=None, filePath=None) -> None:

    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(query="""CREATE TABLE IF NOT EXISTS images(
                user_id INTEGER,
                image_name VARCHAR(100),
                upload_date VARCHAR(30),
                image_hash VARCHAR(50),
                image_type VARCHAR(10),
                image_location VARCHAR(10));""")
            if ImgHash is not None:
                record.imageHash = ImgHash
            else:
                theImage = Image.open(filePath)
                img_hash = DifferenceHash(theImage)
                record.imageHash = str(img_hash)
            
            await cursor.execute(
                 """
                    INSERT INTO images (user_id,
                    image_name,
                    upload_date,
                    image_hash,
                    image_type,
                    image_location)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        record.userId,
                        record.imageName,
                        record.uploadDate,
                        record.imageHash,
                        record.imageType,
                        record.imageLocation
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


async def find_similar_images(db_pool, photo) -> list:
    theImage = Image.open(photo)
    img_hash = DifferenceHash(theImage)
    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("""SELECT user_id,  
                                 image_name,  
                                 upload_date, 
                                 image_location 
                                 FROM images 
                                 WHERE image_hash = (%s);""", [str(img_hash)])
            records = await cursor.fetchall()
    return records if records else []


