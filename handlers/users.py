from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from database.image import (find_similar_images, ImageRecord,
                            append_image_record)
import logging
import io
import aiohttp
#from api.model import predict_bytes

logger = logging.getLogger(__name__)
router = Router()


async def handle_image_message(message: Message, db_pool, API_URL, admin_ids: list):
    buffer = io.BytesIO()
    Bot = message.bot
    file = await Bot.get_file(message.photo[-1].file_id)
    file_path = file.file_path

    await Bot.download_file(file_path, 'tmp_image.jpg')
#    try:
#    predict = predict_bytes('/home/anvar/my_bot/tmp_image.jpg')
#    except:
#        logger.info("Prediction failed")
    data = aiohttp.FormData()
    data.add_field("file", "/home/anvar/my_bot/tmp_image.jpg", filename="tmp_image.jpg", content_type="image/jpeg")

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, data=data) as resp:
            result = await resp.json()

    if result['class'] in ["Equip", "Selfie"]:
        #await Bot.forward_message(chat_id=str(admin_ids[0]),
        #                      from_chat_id=message.chat.id,
        #                      message_id=message.message_id)
        #await Bot.send_message(chat_id=str(admin_ids[0]), text=f"Class: {result['class']}")

        await Bot.download_file(file_path, buffer)
        buffer.seek(0)
        similar = await find_similar_images(db_pool, buffer)
        if similar is not None:
            await message.forward(chat_id=str(admin_ids[0]))
            if similar.imageLocation == 'telegram':
                await Bot.send_photo(
                    chat_id=str(admin_ids[0]),
                    photo=similar.imageName,
                    caption=f"Similar image found from user {similar.userName}: "
                            f"uploaded on {similar.uploadDate}," 
                            f"timestamp: {similar.unix_date}")
            else:
                await Bot.send_message(
                    chat_id=str(admin_ids[0]),
                    text=f"Similar image found from user {similar.userName}: "
                        f"uploaded on {similar.uploadDate}, "
                        f"location: {similar.imageLocation}")
        image = ImageRecord(
            userId=message.from_user.id,
            userName=message.from_user.full_name + "(@" + message.from_user.username + ")" if message.from_user.username else message.from_user.full_name,
            imageName=message.photo[-1].file_id,
            uploadDate=message.date.strftime("%d-%m-%Y %H:%M:%S"),
            imageHash="",
            imageType="",
            imageLocation="telegram",
            unix_date=message.date.timestamp(),
            im_predicted_class=result['class'],
            chat_id=message.chat.id, 
            message_id=message.message_id)
        await append_image_record(db_pool, image, ImgHash=None, filePath=buffer)


@router.message(F.photo)
async def handle_photos(message: Message, db_pool, admin_ids: list, API_URL, album: list = None):
    if album:
        for msg in album:
            await handle_image_message(msg, db_pool, API_URL, admin_ids)
    else:
        await handle_image_message(message, db_pool, API_URL, admin_ids)


@router.message(Command(commands='help'))
async def process_help_command(message: Message):
    await message.answer(text="This is the help command response.")


