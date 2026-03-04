import logging
from urllib.parse import quote

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from database.image import ImageRecord

logger = logging.getLogger(__name__)


# Функция, возвращающая безопасную строку `conninfo` для подключения к PostgreSQL
def build_pg_conninfo(
    db_name: str,
    host: str,
    port: int,
    user: str,
    password: str,
) -> str:
    conninfo = (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{db_name}"
    )
    logger.debug(f"Building PostgreSQL connection string (password omitted): "
                 f"postgresql://{quote(user, safe='')}@{host}:{port}/{db_name}")
    return conninfo


# Функция, логирующая версию СУБД, к которой происходит подключение
async def log_db_version(connection: AsyncConnection) -> None:
    try:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT version();")
            db_version = await cursor.fetchone()
            logger.info(f"Connected to PostgreSQL version: {db_version[0]}")
    except Exception as e:
        logger.warning("Failed to fetch DB version: %s", e)


# Функция, возвращающая открытое соединение с СУБД PostgreSQL
async def get_pg_connection(
    db_name: str,
    host: str,
    port: int,
    user: str,
    password: str,
) -> AsyncConnection:
    conninfo = build_pg_conninfo(db_name, host, port, user, password)
    connection: AsyncConnection | None = None

    try:
        connection = await AsyncConnection.connect(conninfo=conninfo)
        await log_db_version(connection)
        return connection
    except Exception as e:
        logger.exception("Failed to connect to PostgreSQL: %s", e)
        if connection:
            await connection.close()
        raise


# Функция, возвращающая пул соединений с СУБД PostgreSQL
async def get_pg_pool(
    db_name: str,
    host: str,
    port: int,
    user: str,
    password: str,
    min_size: int = 1,
    max_size: int = 3,
    timeout: float | None = 10.0,
) -> AsyncConnectionPool:
    conninfo = build_pg_conninfo(db_name, host, port, user, password)
    db_pool: AsyncConnectionPool | None = None

    try:
        db_pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=False,
        )

        await db_pool.open()

        async with db_pool.connection() as connection:
            await log_db_version(connection)

        return db_pool
    except Exception as e:
        logger.exception("Failed to initialize PostgreSQL pool: %s", e)
        if db_pool and not db_pool.closed:
            await db_pool.close()
        raise

async def GetChatsList(db_pool):
    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT chat_id FROM chats;")
            rows = await cursor.fetchall()
            logger.info(f"Fetched {len(rows)} chat IDs from the database.")
            return rows

async def AddChat(db_pool, chat: dict):
    async with db_pool.connection() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO chats (chat_id, chat_type, chat_name) 
                VALUES (%s, %s, %s) ON CONFLICT (chat_id) DO NOTHING;""",
                (chat['chat_id'], chat['chat_type'], chat['chat_name'])
            )
            logger.info(f"Added chat ID {chat['chat_id']} to the database.")