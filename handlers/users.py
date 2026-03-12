from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.image import (find_similar_images, ImageRecord,
                            append_image_record, get_user_language)
from lexicon.lexicon import LEXICON_RU, LEXICON_UZ
import logging
import io
import aiohttp
import datetime
import tempfile
import os
#from api.model import predict_bytes

logger = logging.getLogger(__name__)
router = Router()


class CustomerListStates(StatesGroup):
    waiting_for_list = State()


async def handle_image_message(message: Message, db_pool, API_URL, admin_ids: list):
    buffer = io.BytesIO()
    Bot = message.bot
    # determine user language for lexicon lookups
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'ru' else LEXICON_UZ
    file = await Bot.get_file(message.photo[-1].file_id)
    file_path = file.file_path
    
    try:
        await Bot.download_file(file_path, destination=buffer)
        file_content = buffer.getvalue()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            tmp_file.write(file_content)
            tmp_file_path = tmp_file.name
   
        data = aiohttp.FormData()
        data.add_field("file", tmp_file_path, filename="tmp_image.jpg", content_type="image/jpeg")

        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, data=data) as resp:
                result = await resp.json()
    except Exception as e:
        logger.error(f"{lexicon['error_processing_image']} {e}")
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.error(f"Error deleting temporary file: {e}")

    # Check if caption contains 'Закончил' and perform equipment count validation
    if message.caption and 'Закончил' in message.caption:
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        current_weekday = datetime.datetime.now().isocalendar()[2]
    
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                # Count Equip images uploaded today by this user
                await cursor.execute(
                    "SELECT COUNT(*) FROM images WHERE user_id = %s AND upload_date LIKE %s AND im_predicted_class = %s",
                    (message.from_user.id, f"{today}%", 'Equip')
                )
                equip_images_count = await cursor.fetchone()
                
                # Count records in equip table for this user and current weekday
                await cursor.execute(
                    "SELECT COUNT(*) FROM equip WHERE agent_id = %s AND visit_day = %s",
                    (message.from_user.id, current_weekday)
                )
                equip_records_count = await cursor.fetchone()
                
                # If counts don't match, notify admins
                if equip_images_count[0] != equip_records_count[0]:
                    for admin_id in admin_ids:
                        await Bot.send_message(
                            chat_id=str(admin_id),
                            text=f"⚠️ User {message.from_user.full_name} (ID: {message.from_user.id}) finished work but equipment counts don't match!\n"
                                f"Equip images uploaded today: {equip_images_count[0]}\n"
                                f"Expected equipment records: {equip_records_count[0]}"
                        )

    if result['class'] == 'Selfie':
        today = datetime.datetime.now().strftime("%d-%m-%Y")
        async with db_pool.connection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM images WHERE user_id = %s AND upload_date LIKE %s", (message.from_user.id, f"{today}%"))
                count = await cursor.fetchone()
                if count[0] == 0:
                    current_weekday = datetime.datetime.now().isocalendar()[2]
                    await cursor.execute("SELECT COUNT(cust_name) FROM equip WHERE visit_day = %s AND agent_id = %s", (current_weekday, message.from_user.id))
                    equip_count = await cursor.fetchone()
                    if equip_count[0] != 0:
                        keyboard = InlineKeyboardBuilder()
                        keyboard.button(text=lexicon['yes'], callback_data=f"show_customers_{message.from_user.id}")
                        keyboard.button(text=lexicon['no'], callback_data="cancel_customers")
                        await Bot.send_message(
                            chat_id=str(message.from_user.id),
                            text=f"{lexicon['total_customers_this_week']} {equip_count[0]}\n\n{lexicon['want_see_customers']}",
                            reply_markup=keyboard.as_markup()
                        )
                
    
    await Bot.download_file(file_path, buffer)
    buffer.seek(0)
    similar = await find_similar_images(db_pool, buffer)
    if similar is not None:
        await message.forward(chat_id=str(admin_ids[0]))
        if similar.imageLocation == 'telegram':
            await Bot.send_photo(
                chat_id=str(admin_ids[0]),
                photo=similar.imageName,
                caption=f"{lexicon['similar_image_found']} {similar.userName}: "
                        f"{lexicon['uploaded_on']} {similar.uploadDate}, "
                        f"{lexicon['timestamp']}: {similar.unix_date}")
        else:
            await Bot.send_message(
                chat_id=str(admin_ids[0]),
                text=f"{lexicon['similar_image_found']} {similar.userName}: "
                    f"{lexicon['uploaded_on']} {similar.uploadDate}, "
                    f"{lexicon['location']}: {similar.imageLocation}")
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
        message_id=message.message_id,
        caption=message.caption if message.caption else "")
    await append_image_record(db_pool, image, ImgHash=None, filePath=buffer)

       
@router.message(F.photo)
async def handle_photos(message: Message, db_pool, admin_ids: list, API_URL, album: list = None):
    if album:
        for msg in album:
            await handle_image_message(msg, db_pool, API_URL, admin_ids)
    else:
        await handle_image_message(message, db_pool, API_URL, admin_ids)


@router.callback_query(F.data.startswith("show_customers_"))
async def show_customer_list(callback: CallbackQuery, db_pool):
    user_id = int(callback.data.split("_")[-1])
    user_lang = await get_user_language(db_pool, callback.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'RU' else LEXICON_UZ
    
    if callback.from_user.id != user_id:
        await callback.answer(lexicon['this_is_not_your_query'], show_alert=True)
        return
    
    await callback.answer()
    
    current_weekday = datetime.datetime.now().isocalendar()[2]
    async with db_pool.connection() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT cust_name FROM equip WHERE visit_day = %s AND agent_id = %s", (current_weekday, user_id))
            customers = await cursor.fetchall()
    
    if customers:
        text = f"{lexicon['customers_list']}\n"
        for i, cust in enumerate(customers, 1):
            text += f"{i}. {cust[0]}\n"
        await callback.message.answer(text)
    else:
        await callback.message.answer(lexicon['no_customers_found'])


@router.callback_query(F.data == "cancel_customers")
async def cancel_customers(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@router.message(Command(commands='help'))
async def process_help_command(message: Message, db_pool):
    user_lang = await get_user_language(db_pool, message.from_user.id)
    lexicon = LEXICON_RU if user_lang == 'RU' else LEXICON_UZ
    await message.answer(text=lexicon['/help'])


