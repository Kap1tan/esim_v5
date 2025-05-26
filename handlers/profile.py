# handlers/profile.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.inline import get_profile_keyboard, get_back_to_main_keyboard
from texts import TEXTS
from config import ESIM_ACCESS_CODE
from utils.esim_client import ESIMAccessClient
import logging

router = Router()
logger = logging.getLogger(__name__)

# Создаем экземпляр клиента eSIM Access
esim_client = ESIMAccessClient(ESIM_ACCESS_CODE)

# Хранилище для заказов пользователей
# В реальном приложении лучше использовать базу данных
user_orders = {}


class ProfileStates(StatesGroup):
    viewing_profile = State()
    viewing_esim = State()


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery, state: FSMContext):
    """Показать профиль пользователя"""
    user_id = callback.from_user.id

    # Получаем заказы пользователя (заглушка)
    orders = user_orders.get(user_id, [])

    if not orders:
        # Если у пользователя нет заказов
        profile_text = f"{TEXTS['profile']}\n\nУ вас пока нет активированных eSIM. Нажмите на кнопку «Купить eSIM», чтобы приобрести новую."
        keyboard = get_profile_keyboard()
    else:
        # Формируем текст с имеющимися eSIM
        profile_text = TEXTS['profile'] + "\n\n"

        for i, order in enumerate(orders):
            order_no = order.get('order_no', 'Неизвестный')
            country = order.get('country', 'Неизвестная страна')
            date = order.get('date', 'Неизвестная дата')

            profile_text += f"{i + 1}. eSIM {country} - {date}\n"

        # Создаем клавиатуру с eSIM
        builder = InlineKeyboardBuilder()

        for i, order in enumerate(orders):
            country = order.get('country', 'Неизвестная страна')
            builder.row(
                InlineKeyboardButton(text=f"eSIM {country}", callback_data=f"esim_{i}")
            )

        builder.row(
            InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
        )

        keyboard = builder.as_markup()

    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text=profile_text,
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                text=profile_text,
                reply_markup=keyboard
            )
    except Exception as e:
        # В случае ошибки просто отправляем новое сообщение
        await callback.message.answer(
            text=profile_text,
            reply_markup=keyboard
        )

    await state.set_state(ProfileStates.viewing_profile)
    await callback.answer()


@router.callback_query(ProfileStates.viewing_profile, F.data.startswith("esim_"))
async def show_esim_details(callback: CallbackQuery, state: FSMContext):
    """Показать детали eSIM"""
    user_id = callback.from_user.id

    # Получаем индекс eSIM
    esim_index = int(callback.data.split('_')[1])

    # Получаем данные о заказе
    orders = user_orders.get(user_id, [])

    if not orders or esim_index >= len(orders):
        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    text="eSIM не найдена. Возможно, она была удалена.",
                    reply_markup=get_back_to_main_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text="eSIM не найдена. Возможно, она была удалена.",
                    reply_markup=get_back_to_main_keyboard()
                )
        except Exception:
            await callback.message.answer(
                text="eSIM не найдена. Возможно, она была удалена.",
                reply_markup=get_back_to_main_keyboard()
            )
        await callback.answer()
        return

    order = orders[esim_index]
    order_no = order.get('order_no', '')

    # Получаем данные eSIM через API
    profiles = esim_client.query_order(order_no)

    if not profiles:
        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    text="Не удалось получить информацию об eSIM. Пожалуйста, попробуйте позже.",
                    reply_markup=get_back_to_main_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text="Не удалось получить информацию об eSIM. Пожалуйста, попробуйте позже.",
                    reply_markup=get_back_to_main_keyboard()
                )
        except Exception:
            await callback.message.answer(
                text="Не удалось получить информацию об eSIM. Пожалуйста, попробуйте позже.",
                reply_markup=get_back_to_main_keyboard()
            )
        await callback.answer()
        return

    # Берем первый профиль
    profile = profiles[0]

    # Формируем информацию о профиле
    ac = profile.get("ac", "")  # Activation Code
    qr_code_url = profile.get("qrCodeUrl", "")
    iccid = profile.get("iccid", "")
    status = profile.get("status", "")

    # Проверяем статус
    status_text = "Активна" if status == "ACTIVE" else "Не активирована"

    esim_details = f"""
eSIM #{esim_index + 1}

ICCID: {iccid}
Статус: {status_text}
Код активации: {ac}

QR-код для активации: {qr_code_url}

Для активации отсканируйте QR-код или введите код активации в настройках вашего устройства.
"""

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()

    # Если eSIM не активирована, добавляем кнопку активации
    if status != "ACTIVE":
        builder.row(
            InlineKeyboardButton(text="📲 Активировать", callback_data=f"activate_esim_{esim_index}")
        )

    builder.row(
        InlineKeyboardButton(text="↩️ Назад к профилю", callback_data="profile")
    )

    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text=esim_details,
                reply_markup=builder.as_markup(),
                disable_web_page_preview=False
            )
        else:
            await callback.message.edit_text(
                text=esim_details,
                reply_markup=builder.as_markup(),
                disable_web_page_preview=False
            )
    except Exception:
        await callback.message.answer(
            text=esim_details,
            reply_markup=builder.as_markup(),
            disable_web_page_preview=False
        )

    await state.set_state(ProfileStates.viewing_esim)
    await callback.answer()


# Заглушка для активации eSIM
@router.callback_query(ProfileStates.viewing_esim, F.data.startswith("activate_esim_"))
async def activate_esim(callback: CallbackQuery, state: FSMContext):
    """Активация eSIM"""
    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text="eSIM активируется автоматически при установке. Следуйте инструкциям в разделе «Как установить eSIM».",
                reply_markup=get_back_to_main_keyboard()
            )
        else:
            await callback.message.edit_text(
                text="eSIM активируется автоматически при установке. Следуйте инструкциям в разделе «Как установить eSIM».",
                reply_markup=get_back_to_main_keyboard()
            )
    except Exception:
        await callback.message.answer(
            text="eSIM активируется автоматически при установке. Следуйте инструкциям в разделе «Как установить eSIM».",
            reply_markup=get_back_to_main_keyboard()
        )
    await callback.answer()


# Функция для сохранения информации о заказе
def save_order(user_id, order_no, country, package_name):
    """Сохраняет информацию о заказе пользователя"""
    from datetime import datetime

    order_info = {
        'order_no': order_no,
        'country': country,
        'package_name': package_name,
        'date': datetime.now().strftime('%d.%m.%Y')
    }

    if user_id not in user_orders:
        user_orders[user_id] = []

    user_orders[user_id].append(order_info)