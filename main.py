import asyncio
import logging
from config.config import Config, load_config
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers import user  # Импортируем модуль с хэндлерами



config: Config = load_config()
logger = logging.getLogger(__name__)

async def main():
    logging.basicConfig(
            level=logging.DEBUG,
            format='[%(asctime)s] #%(levelname)-8s %(filename)s:'
            '%(lineno)d - %(name)s - %(message)s'
    )

    config: Config = load_config()
    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()


    # Инициализируем другие объекты (пул соединений с БД, кеш и т.п.)
    # ...

    # Помещаем нужные объекты в workflow_data диспетчера
    # dp.workflow_data.update('admin_ids': config.bot.admin_ids)

    # Настраиваем главное меню бота
    # await set_main_menu(bot)

    # Регистриуем роутеры
    logger.info('Подключаем роутеры')
    dp.include_router(user.router)
    # ...

    # Регистрируем миддлвари
    logger.info('Подключаем миддлвари')
    # ...

    # Пропускаем накопившиеся апдейты и запускаем polling
    # await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


asyncio.run(main())
