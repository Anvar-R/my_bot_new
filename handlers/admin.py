from aiogram import Router
from aiogram.filters import Command, CommandStart, BaseFilter
from aiogram.types import Message
from lexicon.lexicon import LEXICON_RU
from database.image import create_database
import time
import logging


# Собственный фильтр, проверяющий юзера на админа
class IsAdmin(BaseFilter):
    def __init__(self, admin_ids: list[int]) -> None:
        # В качестве параметра фильтр принимает список с целыми числами 
        self.admin_ids = admin_ids

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in self.admin_ids


logger = logging.getLogger(__name__)
# Инициализируем роутер уровня модуля
router = Router()


# Этот хэндлер срабатывает на команду /start
@router.message(CommandStart())
async def process_start_command(message: Message):
    await message.answer(text=LEXICON_RU['/start'])


# Этот хэндлер срабатывает на команду /help
@router.message(Command(commands='help'))
async def process_help_command(message: Message):
    await message.answer(text=LEXICON_RU['/help'])

@router.message(Command(commands='data'))
async def process_data_command(message: Message, db_pool):
    bot = message.bot
    await bot.send_message(chat_id=message.from_user.id, text='Начинаю заполнение базы данных изображениями...')
    logger.info('Recieved /data command from admin user. Starting database population.')
    startTime = time.monotonic()
    await create_database(db_pool)
    await bot.send_message(chat_id=message.from_user.id, 
        text=f'Заполнение базы данных завершено. Затрачено времени: {time.monotonic() - startTime:.2f} секунд.')
    logger.info('Database population completed.')
    