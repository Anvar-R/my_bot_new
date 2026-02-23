import asyncio
import logging
import os
from config.config import Config, load_config
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers import admin, users  # Импортируем модуль с хэндлерами
from middleware.user import AlbumMiddleware
import psycopg_pool
from database.database import get_pg_pool
from database.image import initialize_database
import selectors
import signal

# config: Config = load_config()
logger = logging.getLogger(__name__)

def shutdown_handler(sig, frame):
    logger.info("Bot shutting down")
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


async def main():
    logging.basicConfig(
            level=logging.DEBUG,
            format='[%(asctime)s] #%(levelname)-8s %(filename)s:'
            '%(lineno)d - %(name)s - %(message)s'
    )
    log_file = logging.FileHandler('my_bot.log', mode='w', encoding='utf-8')
    log_file.setLevel(logging.DEBUG)
    logger.addHandler(log_file)

    config: Config = load_config()
    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # Инициализируем другие объекты (пул соединений с БД, кеш и т.п.)
    db_pool: psycopg_pool.AsyncConnectionPool = await get_pg_pool(
        db_name=config.db.name,
        host=config.db.host,
        port=config.db.port,
        user=config.db.user,
        password=config.db.password
    )
    dp['IMAGE_PATH'] = config.image.image_path
    # Настраиваем главное меню бота
    # await set_main_menu(bot)
    dp.workflow_data.update({'db_pool': db_pool}, 
                            API_URL=config.API_URL)
    # Инициализируем базу данных
    await initialize_database(db_pool)    
    # Регистриуем роутеры
    logger.info('Подключаем роутеры')
    dp.include_router(admin.router)
    admin.router.message.filter(admin.IsAdmin(config.bot.admin_ids))
    
    dp.include_router(users.router)
    users.router.message.filter(~admin.IsAdmin(config.bot.admin_ids))
    # Регистрируем миддлвари
    # logger.info('Подключаем миддлвари')
    # ...
    
    users.router.message.outer_middleware(AlbumMiddleware())
    # Пропускаем накопившиеся апдейты и запускаем polling
    # await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, 
                           db_pool=db_pool, 
                           admin_ids=config.bot.admin_ids) 

if os.name == 'nt':
    asyncio.run(main(),  loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
else:
    asyncio.run(main())
