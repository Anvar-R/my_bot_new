from aiogram import Router
from aiogram.filters import Command, CommandStart, BaseFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from lexicon.lexicon import LEXICON_RU, LEXICON_UZ
from database.image import create_database, insert_routes, insert_equip, get_user_language
from database.excel_parser import parse_route_excel, parse_equip_excel
import time
import logging
import tempfile
import os
from io import BytesIO


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


# FSM states for route update command
class RouteUpdate(StatesGroup):
    waiting_for_file = State()


# FSM states for equipment update command
class EquipmentUpdate(StatesGroup):
    waiting_for_file = State()


# Этот хэндлер срабатывает на команду /start
@router.message(CommandStart())
async def process_start_command(message: Message, db_pool):
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    await message.answer(text=lexicon['/start'])


# Этот хэндлер срабатывает на команду /help
@router.message(Command(commands='help'))
async def process_help_command(message: Message, db_pool):
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    await message.answer(text=lexicon['/help'])

@router.message(Command(commands='data'))
async def process_data_command(message: Message, db_pool):
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    bot = message.bot
    await bot.send_message(chat_id=message.from_user.id, text=lexicon['starting_db_population'])
    logger.info('Recieved /data command from admin user. Starting database population.')
    startTime = time.monotonic()
    await create_database(db_pool)
    elapsed_time = time.monotonic() - startTime
    await bot.send_message(chat_id=message.from_user.id, 
        text=f"{lexicon['db_population_completed']} {elapsed_time:.2f} {lexicon['seconds']}")
    logger.info('Database population completed.')


@router.message(Command(commands='updateroute'))
async def process_updateroute_command(message: Message, state: FSMContext, db_pool):
    """Handle /updateroute command - ask admin to send Excel file"""
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    bot = message.bot
    await bot.send_message(
        chat_id=message.from_user.id,
        text=f"{lexicon['send_excel_route']}"
             'Требуемые колонки:\n'
             '• agent_id (целое число)\n'
             '• reg_name (текст, макс 50 символов)\n'
             '• visit_day (целое число)'
    )
    await state.set_state(RouteUpdate.waiting_for_file)
    logger.info(f'Received /updateroute command from admin {message.from_user.id}')


@router.message(RouteUpdate.waiting_for_file)
async def process_route_file(message: Message, state: FSMContext, db_pool):
    """Handle Excel file upload for route data"""
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    bot = message.bot

    # Check if message contains a document
    if not message.document:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='❌ Пожалуйста, отправьте файл Excel (.xlsx).'
        )
        return

    # Check file extension
    file_name = message.document.file_name or ''
    if not file_name.lower().endswith(('.xlsx', '.xls')):
        await bot.send_message(
            chat_id=message.from_user.id,
            text='❌ Файл должен быть в формате Excel (.xlsx или .xls).'
        )
        return

    temp_file_path = None
    try:
        # Download file from Telegram
        file = await bot.get_file(message.document.file_id)

        # Download to BytesIO
        file_bytes = BytesIO()
        await bot.download(file, destination=file_bytes)
        file_content = file_bytes.getvalue()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_content)

        # Parse Excel file from temp file
        routes_data = await parse_route_excel(temp_file_path)

        # Insert data into database
        inserted_count = await insert_routes(db_pool, routes_data)

        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'✅ Успешно загружено {inserted_count} маршрутов в базу данных.'
        )
        logger.info(f'Successfully processed route file: {inserted_count} routes inserted by admin {message.from_user.id}')

    except ValueError as e:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'❌ Ошибка в формате файла:\n{str(e)}'
        )
        logger.error(f'File format error: {e}')

    except Exception as e:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'❌ Ошибка при обработке файла:\n{str(e)}'
        )
        logger.error(f'Error processing route file: {e}')

    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f'Deleted temporary file: {temp_file_path}')
            except Exception as e:
                logger.error(f'Error deleting temporary file: {e}')

        # Clear FSM state
        await state.clear()


@router.message(Command(commands='equipment'))
async def process_equipment_command(message: Message, state: FSMContext, db_pool):
    """Handle /equipment command - ask admin to send Excel file"""
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    bot = message.bot
    await bot.send_message(
        chat_id=message.from_user.id,
        text=f"{lexicon['send_excel_equip']}"
             'Требуемые колонки:\n'
             '• agent_id (целое число)\n'
             '• cust_name (текст, макс 50 символов)\n'
             '• equip_type (текст, макс 20 символов)\n'
             '• visit_day (целое число)'
    )
    await state.set_state(EquipmentUpdate.waiting_for_file)
    logger.info(f'Received /equipment command from admin {message.from_user.id}')


@router.message(EquipmentUpdate.waiting_for_file)
async def process_equipment_file(message: Message, state: FSMContext, db_pool):
    """Handle Excel file upload for equipment data"""
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    bot = message.bot

    # Check if message contains a document
    if not message.document:
        await bot.send_message(
            chat_id=message.from_user.id,
            text='❌ Пожалуйста, отправьте файл Excel (.xlsx).'
        )
        return

    # Check file extension
    file_name = message.document.file_name or ''
    if not file_name.lower().endswith(('.xlsx', '.xls')):
        await bot.send_message(
            chat_id=message.from_user.id,
            text='❌ Файл должен быть в формате Excel (.xlsx или .xls).'
        )
        return

    temp_file_path = None
    try:
        # Download file from Telegram
        file = await bot.get_file(message.document.file_id)

        # Download to BytesIO
        file_bytes = BytesIO()
        await bot.download(file, destination=file_bytes)
        file_content = file_bytes.getvalue()

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_content)

        # Parse Excel file from temp file
        equip_data = await parse_equip_excel(temp_file_path)

        # Insert data into database
        inserted_count = await insert_equip(db_pool, equip_data)

        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'✅ Успешно загружено {inserted_count} записей оборудования в базу данных.'
        )
        logger.info(f'Successfully processed equipment file: {inserted_count} records inserted by admin {message.from_user.id}')

    except ValueError as e:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'❌ Ошибка в формате файла:\n{str(e)}'
        )
        logger.error(f'File format error: {e}')

    except Exception as e:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f'❌ Ошибка при обработке файла:\n{str(e)}'
        )
        logger.error(f'Error processing equipment file: {e}')

    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f'Deleted temporary file: {temp_file_path}')
            except Exception as e:
                logger.error(f'Error deleting temporary file: {e}')

        # Clear FSM state
        await state.clear()