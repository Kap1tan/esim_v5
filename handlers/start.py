# handlers/start.py

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from keyboards.inline import get_start_keyboard
from texts import TEXTS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    # Отправляем приветственное сообщение без картинки
    await message.answer(
        text=TEXTS["welcome"],
        reply_markup=get_start_keyboard()
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат к главному меню"""
    try:
        # Проверяем, является ли текущее сообщение изображением
        if callback.message.photo:
            # Удаляем сообщение с фото и отправляем текст
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["welcome"],
                reply_markup=get_start_keyboard()
            )
        else:
            # Просто редактируем текст
            await callback.message.edit_text(
                text=TEXTS["welcome"],
                reply_markup=get_start_keyboard()
            )
    except Exception as e:
        # В случае ошибки пробуем удалить и отправить новое сообщение
        try:
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["welcome"],
                reply_markup=get_start_keyboard()
            )
        except Exception as e2:
            # Если и это не сработало, просто отправляем новое сообщение
            await callback.message.answer(
                text=TEXTS["welcome"],
                reply_markup=get_start_keyboard()
            )

    await callback.answer()