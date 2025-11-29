from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.image import find_similar_images
import logging
import asyncio
import io

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.photo)
async def handle_image_message(message: Message, db_pool, admin_ids: list):
    buffer = io.BytesIO()
    Bot = message.bot
    file = await Bot.get_file(message.photo[-1].file_id)
    file_path = file.file_path
    await Bot.download_file(file_path, buffer)
    buffer.seek(0)
    similar = await find_similar_images(db_pool, buffer)
    if len(similar) > 0:
        await Bot.send_photo(
            chat_id=admin_ids[0],
            photo=message.photo[-1].file_id)
        await message.answer(text=' '.join(similar[0]))

            
@router.message(Command(commands='help'))
async def process_help_command(message: Message):
    await message.answer(text="This is the help command response.")


