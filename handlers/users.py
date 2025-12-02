from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.image import find_similar_images, ImageRecord, append_image_record
import logging
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
            chat_id=str(admin_ids[0]),
            photo=message.photo[-1].file_id)
        await Bot.send_message(
            chat_id=str(admin_ids[0]),
            text=f"Similar image found from user {similar[0][0]}: "
                 f"{similar[0][1]}, uploaded on {similar[0][2]}, "
                 f"location: {similar[0][3]}")
    image = ImageRecord(
        userId=message.from_user.id,
        imageName=message.photo[-1].file_id,
        uploadDate=message.date.strftime("%d-%m-%Y %H:%M:%S"),
        imageHash="",
        imageType="",
        imageLocation="telegram")
    await append_image_record(db_pool, image, ImgHash=None, filePath=buffer)



            
@router.message(Command(commands='help'))
async def process_help_command(message: Message):
    await message.answer(text="This is the help command response.")


