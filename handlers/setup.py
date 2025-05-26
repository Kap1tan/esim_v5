# handlers/setup.py

from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards.inline import get_feedback_keyboard
from texts import TEXTS

router = Router()


@router.callback_query(F.data == "setup")
async def show_setup(callback: CallbackQuery):
    """Показать инструкцию по установке eSIM"""
    await callback.message.edit_text(
        text=f"{TEXTS['setup_menu']}\n\n{TEXTS['feedback_question']}",
        reply_markup=get_feedback_keyboard()
    )
    await callback.answer()