from aiogram import Router, F
from aiogram.types import Message


router = Router()

@router.message(F.image)
async def handle_image_message(message: Message):
    