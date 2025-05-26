# handlers/buying.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from aiogram.filters.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from keyboards.inline import (
    get_buy_esim_keyboard,
    get_countries_keyboard,
    get_packages_keyboard,
    get_days_selection_keyboard,
    get_confirm_keyboard,
    get_payment_done_keyboard,
    get_back_to_countries_keyboard,
    get_back_to_main_keyboard,
    is_daily_package,
    deduplicate_packages
)
from config import REGIONS, COUNTRY_CODES, ESIM_ACCESS_CODE
from texts import TEXTS
from utils.esim_client import ESIMAccessClient
from utils.currency import currency_converter
import asyncio
import logging

# Импортируем функцию сохранения заказа
try:
    from handlers.profile import save_order
except ImportError:
    # Если не удается импортировать, создаем заглушку
    def save_order(user_id, order_no, country, package_name):
        pass

router = Router()
logger = logging.getLogger(__name__)

# Создаем экземпляр клиента eSIM Access
esim_client = ESIMAccessClient(ESIM_ACCESS_CODE)


# Определяем состояния FSM для процесса покупки
class BuyingStates(StatesGroup):
    selecting_country = State()
    selecting_package = State()
    selecting_days = State()  # Новое состояние для выбора дней
    confirming_purchase = State()
    payment_processing = State()


# Добавляем обработчик для неактивных кнопок навигации и разделителя
@router.callback_query(F.data.in_(["navigation_disabled", "page_info", "separator"]))
async def handle_disabled_navigation(callback: CallbackQuery):
    """Обработчик для неактивных кнопок навигации и разделителя"""
    await callback.answer()


@router.callback_query(F.data == "buy_esim")
async def buy_esim(callback: CallbackQuery, state: FSMContext):
    """Обработчик для покупки eSIM - выбор региона"""
    logger.info(f"User {callback.from_user.id} clicked buy_esim")

    # Очищаем данные состояния
    await state.clear()

    try:
        # Проверяем, есть ли изображение в текущем сообщении
        if callback.message.photo:
            # Удаляем сообщение с фото и отправляем новое
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["buy_esim"],
                reply_markup=get_buy_esim_keyboard()
            )
        else:
            # Редактируем текущее сообщение
            await callback.message.edit_text(
                text=TEXTS["buy_esim"],
                reply_markup=get_buy_esim_keyboard()
            )
        logger.info("Successfully sent buy_esim menu")
    except Exception as e:
        logger.error(f"Error in buy_esim: {e}")
        # В случае ошибки пробуем удалить и отправить новое сообщение
        try:
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["buy_esim"],
                reply_markup=get_buy_esim_keyboard()
            )
            logger.info("Successfully sent buy_esim menu after error recovery")
        except Exception as e2:
            logger.error(f"Failed to recover from error in buy_esim: {e2}")
            await callback.answer("Произошла ошибка. Попробуйте еще раз.")
            return

    await callback.answer()


@router.callback_query(F.data.startswith("region_"))
async def select_region(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора региона"""
    # Правильно извлекаем ключ региона
    region_key = callback.data.replace("region_", "")
    logger.info(f"User {callback.from_user.id} selected region: {region_key}")

    if region_key not in REGIONS:
        logger.error(f"Unknown region: {region_key}")
        await callback.answer("Неизвестный регион")
        return

    region_data = REGIONS[region_key]
    countries = region_data["countries"]

    # Получаем все страны для региона (включая дополнительные страницы)
    all_countries = countries.copy()
    for page_key in [f"countries_page{i}" for i in range(2, 6)]:
        if page_key in region_data:
            all_countries.extend(region_data[page_key])

    try:
        image_path = region_data.get("image", "")
        keyboard = get_countries_keyboard(region_key, all_countries)

        # Проверяем что содержит текущее сообщение
        if callback.message.photo:
            # Если сообщение содержит фото
            if image_path:
                try:
                    photo = FSInputFile(image_path)
                    await callback.message.edit_media(
                        media=InputMediaPhoto(
                            media=photo,
                            caption=TEXTS["select_country"]
                        ),
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Could not edit media, trying to delete and send new: {e}")
                    # Если не удалось отредактировать media, удаляем и отправляем новое
                    await callback.message.delete()
                    await callback.message.answer(
                        text=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
            else:
                # Если фото есть, но нет пути к изображению - удаляем и отправляем текст
                await callback.message.delete()
                await callback.message.answer(
                    text=TEXTS["select_country"],
                    reply_markup=keyboard
                )
        else:
            # Если сообщение содержит только текст
            if image_path:
                # Если есть путь к изображению - удаляем текст и отправляем с фото
                try:
                    await callback.message.delete()
                    photo = FSInputFile(image_path)
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Could not send photo, sending text: {e}")
                    await callback.message.answer(
                        text=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
            else:
                # Если нет изображения - просто редактируем текст
                await callback.message.edit_text(
                    text=TEXTS["select_country"],
                    reply_markup=keyboard
                )

    except Exception as e:
        logger.error(f"Error in select_region: {e}")
        await callback.answer("Произошла ошибка при загрузке региона")
        return

    await callback.answer()
    await state.set_state(BuyingStates.selecting_country)


@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    """Обработчик пагинации стран"""
    try:
        parts = callback.data.split("_")
        region_key = "_".join(parts[1:-1])  # Все части кроме первой и последней
        page = int(parts[-1])  # Последняя часть - номер страницы
    except ValueError:
        logger.error(f"Invalid pagination data: {callback.data}")
        await callback.answer("Ошибка пагинации")
        return

    if region_key not in REGIONS:
        logger.error(f"Unknown region in pagination: {region_key}")
        await callback.answer("Неизвестный регион")
        return

    region_data = REGIONS[region_key]

    # Получаем все страны для региона (включая дополнительные страницы)
    all_countries = region_data["countries"].copy()
    for page_key in [f"countries_page{i}" for i in range(2, 6)]:
        if page_key in region_data:
            all_countries.extend(region_data[page_key])

    try:
        image_path = region_data.get("image", "")
        keyboard = get_countries_keyboard(region_key, all_countries, page)

        # Проверяем что содержит текущее сообщение
        if callback.message.photo:
            # Если сообщение содержит фото и есть путь к изображению - обновляем media
            if image_path:
                try:
                    photo = FSInputFile(image_path)
                    await callback.message.edit_media(
                        media=InputMediaPhoto(
                            media=photo,
                            caption=TEXTS["select_country"]
                        ),
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Could not edit media, trying to delete and send new: {e}")
                    # Если не удалось отредактировать media, удаляем и отправляем новое
                    await callback.message.delete()
                    await callback.message.answer(
                        text=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
            else:
                # Если фото есть, но нет пути к изображению - удаляем и отправляем текст
                await callback.message.delete()
                await callback.message.answer(
                    text=TEXTS["select_country"],
                    reply_markup=keyboard
                )
        else:
            # Если сообщение содержит только текст
            if image_path:
                # Если есть путь к изображению - удаляем текст и отправляем с фото
                try:
                    await callback.message.delete()
                    photo = FSInputFile(image_path)
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.warning(f"Could not send photo, sending text: {e}")
                    await callback.message.answer(
                        text=TEXTS["select_country"],
                        reply_markup=keyboard
                    )
            else:
                # Если нет изображения - просто редактируем текст
                await callback.message.edit_text(
                    text=TEXTS["select_country"],
                    reply_markup=keyboard
                )

    except Exception as e:
        logger.error(f"Error in handle_pagination: {e}")
        await callback.answer("Ошибка при переключении страницы")
        return

    await callback.answer()


@router.callback_query(BuyingStates.selecting_country, F.data.startswith("country_"))
async def select_country(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора страны"""
    country_name = callback.data.replace("country_", "")
    logger.info(f"User {callback.from_user.id} selected country: {country_name}")

    # Проверяем, есть ли код страны
    if country_name not in COUNTRY_CODES:
        logger.warning(f"Country code not found for: {country_name}")
        # Если код страны не найден
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text=TEXTS["nothing_found"],
                reply_markup=get_buy_esim_keyboard()
            )
        else:
            await callback.message.edit_text(
                text=TEXTS["nothing_found"],
                reply_markup=get_buy_esim_keyboard()
            )
        await callback.answer()
        return

    country_code = COUNTRY_CODES[country_name]

    # Сохраняем информацию о стране
    await state.update_data(
        country_name=country_name,
        country_code=country_code
    )

    # Сначала отвечаем на callback
    await callback.answer()

    # Отправляем сообщение о загрузке
    loading_text = TEXTS["loading_packages"].format(country_name=country_name)

    try:
        # Всегда удаляем предыдущее сообщение и отправляем новое для загрузки
        # Это избегает проблем с редактированием разных типов сообщений
        await callback.message.delete()
        message = await callback.message.answer(text=loading_text)

        # Получаем пакеты для выбранной страны
        packages = esim_client.get_packages_by_country(country_code)
        logger.info(f"Found {len(packages)} packages for {country_name}")

        # Дедуплицируем пакеты
        packages = deduplicate_packages(packages)
        logger.info(f"After deduplication: {len(packages)} packages for {country_name}")

        # Сохраняем пакеты в состоянии
        await state.update_data(packages=packages)

        if not packages:
            # Если пакеты не найдены
            no_packages_text = TEXTS["no_packages"].format(country_name=country_name)
            await message.edit_text(
                text=no_packages_text,
                reply_markup=get_back_to_countries_keyboard(f"region_{country_code}")
            )
            return

        # Отображаем тарифы
        packages_text = TEXTS["choose_package"].format(country_name=country_name)
        await message.edit_text(
            text=packages_text,
            reply_markup=get_packages_keyboard(packages, country_code, country_name, 1)
        )
        await state.set_state(BuyingStates.selecting_package)

    except Exception as e:
        logger.error(f"Error in select_country: {e}")
        # Не пытаемся отвечать на callback если произошла ошибка timeout
        return


# Добавляем новый обработчик пагинации пакетов
@router.callback_query(F.data.startswith("packages_page_"))
async def handle_packages_pagination(callback: CallbackQuery, state: FSMContext):
    """Обработчик пагинации пакетов"""
    try:
        parts = callback.data.split("_")
        country_code = parts[2]
        page = int(parts[3])
    except (ValueError, IndexError):
        logger.error(f"Invalid packages pagination data: {callback.data}")
        await callback.answer("Ошибка пагинации")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    packages = data.get("packages", [])
    country_name = data.get("country_name", "")

    if not packages:
        await callback.answer("Пакеты не найдены")
        return

    try:
        # Отображаем тарифы для выбранной страницы
        packages_text = TEXTS["choose_package"].format(country_name=country_name)
        await callback.message.edit_text(
            text=packages_text,
            reply_markup=get_packages_keyboard(packages, country_code, country_name, page)
        )
    except Exception as e:
        logger.error(f"Error in handle_packages_pagination: {e}")
        await callback.answer("Ошибка при переключении страницы")

    await callback.answer()


# Обновляем обработчик выбора пакета
@router.callback_query(BuyingStates.selecting_package, F.data.startswith("package_"))
async def select_package(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора тарифа"""
    try:
        package_index = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        logger.error(f"Invalid package data: {callback.data}")
        await callback.answer("Ошибка выбора тарифа")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    packages = data.get("packages", [])
    country_name = data.get("country_name", "")
    country_code = data.get("country_code", "")

    if not packages or package_index >= len(packages):
        # Если пакет не найден
        await callback.message.edit_text(
            text="Ошибка: выбранный тариф не найден. Попробуйте снова.",
            reply_markup=get_back_to_countries_keyboard(f"region_{country_code}")
        )
        await callback.answer()
        return

    # Получаем выбранный пакет
    package = packages[package_index]

    # Сохраняем выбранный пакет
    await state.update_data(selected_package=package, package_index=package_index)

    # Проверяем, является ли пакет ежедневным
    if is_daily_package(package):
        # Для ежедневных пакетов предлагаем выбрать количество дней
        days_text = TEXTS["select_days"].format(country_name=country_name)
        await callback.message.edit_text(
            text=days_text,
            reply_markup=get_days_selection_keyboard(package_index)
        )
        await state.set_state(BuyingStates.selecting_days)
    else:
        # Для обычных пакетов сразу переходим к подтверждению
        await show_confirmation(callback, state, package, country_name, country_code)

    await callback.answer()


# Новый обработчик выбора количества дней
@router.callback_query(BuyingStates.selecting_days, F.data.startswith("select_days_"))
async def select_days(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора количества дней для ежедневного тарифа"""
    try:
        parts = callback.data.split("_")
        package_index = int(parts[2])
        selected_days = int(parts[3])
    except (ValueError, IndexError):
        logger.error(f"Invalid days selection data: {callback.data}")
        await callback.answer("Ошибка выбора дней")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    packages = data.get("packages", [])
    country_name = data.get("country_name", "")
    country_code = data.get("country_code", "")
    package = data.get("selected_package", {})

    if not package:
        await callback.answer("Ошибка: пакет не найден")
        return

    # Сохраняем выбранное количество дней
    await state.update_data(selected_days=selected_days)

    # Переходим к подтверждению покупки
    await show_confirmation(callback, state, package, country_name, country_code, selected_days)
    await callback.answer()


async def show_confirmation(callback: CallbackQuery, state: FSMContext, package: dict,
                            country_name: str, country_code: str, selected_days: int = None):
    """Показать подтверждение покупки"""
    # Форматируем детали пакета
    package_name = package.get("name", "Неизвестный тариф")
    volume_bytes = package.get("volume", 0)
    duration = package.get("duration", 0)
    duration_unit = package.get("durationUnit", "DAY")
    price_usd = package.get("price", 0) / 10000  # Преобразование в доллары

    # Преобразование байтов в МБ или ГБ для отображения
    if volume_bytes >= 1073741824:  # 1 ГБ
        volume_str = f"{volume_bytes / 1073741824:.0f}ГБ"
    else:
        volume_str = f"{volume_bytes / 1048576:.0f}МБ"

    # Для ежедневных тарифов с выбранными днями
    if selected_days and is_daily_package(package):
        # Рассчитываем цену за выбранное количество дней
        daily_price_usd = price_usd
        total_price_usd = daily_price_usd * selected_days

        # Формируем название тарифа
        formatted_package_name = f"{volume_str}/день на {selected_days} дней"

        # Конвертируем цену в рубли
        price_rub = currency_converter.calculate_esim_price(total_price_usd)
    else:
        # Для обычных тарифов
        total_price_usd = price_usd

        # Форматирование срока действия
        if duration_unit == "DAY":
            duration_str = f"{duration} дней"
        elif duration_unit == "MONTH":
            duration_str = f"{duration} месяцев"
        else:
            duration_str = f"{duration} {duration_unit}"

        # Формируем название тарифа
        formatted_package_name = f"{volume_str}, {duration_str}"

        # Конвертируем цену в рубли
        price_rub = currency_converter.calculate_esim_price(total_price_usd)

    # Получаем операторов (если есть в API)
    operators = package.get("operators", "Локальные операторы")
    if not operators or operators == "":
        operators = "Локальные операторы"

    # Формируем текст подтверждения
    confirmation_text = TEXTS["confirm_purchase"].format(
        country=country_name,
        package_name=formatted_package_name,
        operators=operators,
        price_rub=price_rub,
        price_usd=f"{total_price_usd:.2f}"
    )

    # Отправляем подтверждение
    await callback.message.edit_text(
        text=confirmation_text,
        reply_markup=get_confirm_keyboard(country_code)
    )

    await state.set_state(BuyingStates.confirming_purchase)


@router.callback_query(F.data == "back_to_packages")
async def back_to_packages_from_days(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку тарифов из выбора дней"""
    # Получаем данные из состояния
    data = await state.get_data()
    packages = data.get("packages", [])
    country_name = data.get("country_name", "")
    country_code = data.get("country_code", "")

    if not packages:
        # Если пакеты не найдены, возвращаемся к выбору регионов
        await callback.message.edit_text(
            text=TEXTS["buy_esim"],
            reply_markup=get_buy_esim_keyboard()
        )
        await callback.answer()
        return

    # Отображаем тарифы (первая страница)
    packages_text = TEXTS["choose_package"].format(country_name=country_name)
    await callback.message.edit_text(
        text=packages_text,
        reply_markup=get_packages_keyboard(packages, country_code, country_name, 1)
    )

    await state.set_state(BuyingStates.selecting_package)
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_packages_"))
async def back_to_packages(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку тарифов"""
    country_code = callback.data.replace("back_to_packages_", "")

    # Получаем данные из состояния
    data = await state.get_data()
    packages = data.get("packages", [])
    country_name = data.get("country_name", "")

    if not packages:
        # Если пакеты не найдены, возвращаемся к выбору регионов
        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    text=TEXTS["buy_esim"],
                    reply_markup=get_buy_esim_keyboard()
                )
            else:
                await callback.message.edit_text(
                    text=TEXTS["buy_esim"],
                    reply_markup=get_buy_esim_keyboard()
                )
        except Exception as e:
            # В случае ошибки просто отправляем новое сообщение
            await callback.message.answer(
                text=TEXTS["buy_esim"],
                reply_markup=get_buy_esim_keyboard()
            )
        await callback.answer()
        return

    # Отображаем тарифы (первая страница)
    packages_text = TEXTS["choose_package"].format(country_name=country_name)

    try:
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                text=packages_text,
                reply_markup=get_packages_keyboard(packages, country_code, country_name, 1)
            )
        else:
            await callback.message.edit_text(
                text=packages_text,
                reply_markup=get_packages_keyboard(packages, country_code, country_name, 1)
            )
    except Exception as e:
        # В случае ошибки просто отправляем новое сообщение
        await callback.message.answer(
            text=packages_text,
            reply_markup=get_packages_keyboard(packages, country_code, country_name, 1)
        )

    await state.set_state(BuyingStates.selecting_package)
    await callback.answer()


# Обновляем обработчик оплаты СБП
@router.callback_query(BuyingStates.confirming_purchase, F.data == "pay_sbp")
async def process_payment_sbp(callback: CallbackQuery, state: FSMContext):
    """Обработчик оплаты по СБП"""
    # Отправляем сообщение о обработке платежа
    await callback.message.edit_text(text=TEXTS["processing_payment"])
    await callback.answer()

    # Получаем данные из состояния
    data = await state.get_data()
    package = data.get("selected_package", {})
    selected_days = data.get("selected_days")

    if not package:
        await callback.message.edit_text(
            text="Ошибка: информация о выбранном тарифе не найдена. Попробуйте снова.",
            reply_markup=get_back_to_main_keyboard()
        )
        return

    # Заказываем eSIM
    package_code = package.get("packageCode", "")
    price = package.get("price", 0)

    # Для ежедневных тарифов с выбранными днями корректируем цену
    if selected_days and is_daily_package(package):
        total_price = price * selected_days
        count = 1  # Заказываем один профиль на выбранное количество дней
    else:
        total_price = price
        count = 1

    order_no = esim_client.order_profile(
        package_code=package_code,
        price=total_price,
        count=count,
        period_num=selected_days if selected_days and is_daily_package(package) else None
    )

    if not order_no:
        # Если заказ не удался
        await callback.message.edit_text(
            text=TEXTS["payment_error"],
            reply_markup=get_back_to_main_keyboard()
        )
        return

    # Сохраняем номер заказа
    await state.update_data(order_no=order_no)

    # Сохраняем информацию о заказе в профиле пользователя
    user_id = callback.from_user.id
    country_name = data.get("country_name", "")
    package_name = package.get("name", "")
    save_order(user_id, order_no, country_name, package_name)

    # Отправляем сообщение об успешной оплате
    await callback.message.edit_text(
        text=TEXTS["payment_success"],
        reply_markup=get_payment_done_keyboard()
    )

    await state.set_state(BuyingStates.payment_processing)


@router.callback_query(BuyingStates.confirming_purchase, F.data == "confirm_purchase")
async def process_payment(callback: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения покупки и оплаты"""
    # Отправляем сообщение о обработке платежа
    await callback.message.edit_text(text=TEXTS["processing_payment"])
    await callback.answer()

    # Получаем данные из состояния
    data = await state.get_data()
    package = data.get("selected_package", {})
    selected_days = data.get("selected_days")

    if not package:
        await callback.message.edit_text(
            text="Ошибка: информация о выбранном тарифе не найдена. Попробуйте снова.",
            reply_markup=get_back_to_main_keyboard()
        )
        return

    # Заказываем eSIM
    package_code = package.get("packageCode", "")
    price = package.get("price", 0)

    # Для ежедневных тарифов с выбранными днями корректируем цену
    if selected_days and is_daily_package(package):
        total_price = price * selected_days
        count = 1  # Заказываем один профиль на выбранное количество дней
    else:
        total_price = price
        count = 1

    order_no = esim_client.order_profile(
        package_code=package_code,
        price=total_price,
        count=count,
        period_num=selected_days if selected_days and is_daily_package(package) else None
    )

    if not order_no:
        # Если заказ не удался
        await callback.message.edit_text(
            text=TEXTS["payment_error"],
            reply_markup=get_back_to_main_keyboard()
        )
        return

    # Сохраняем номер заказа
    await state.update_data(order_no=order_no)

    # Сохраняем информацию о заказе в профиле пользователя
    user_id = callback.from_user.id
    country_name = data.get("country_name", "")
    package_name = package.get("name", "")
    save_order(user_id, order_no, country_name, package_name)

    # Отправляем сообщение об успешной оплате
    await callback.message.edit_text(
        text=TEXTS["payment_success"],
        reply_markup=get_payment_done_keyboard()
    )

    await state.set_state(BuyingStates.payment_processing)


@router.callback_query(BuyingStates.payment_processing, F.data == "show_esim_details")
async def show_esim_details(callback: CallbackQuery, state: FSMContext):
    """Показать детали купленной eSIM"""
    await callback.answer()

    # Отправляем сообщение о получении данных
    await callback.message.edit_text(text=TEXTS["getting_esim_details"])

    # Получаем номер заказа
    data = await state.get_data()
    order_no = data.get("order_no", "")

    if not order_no:
        await callback.message.edit_text(
            text="Ошибка: информация о заказе не найдена.",
            reply_markup=get_back_to_main_keyboard()
        )
        await state.clear()
        return

    # Ждем, пока eSIM будет готова (может занять некоторое время)
    profiles = []
    for _ in range(5):  # Максимум 5 попыток
        profiles = esim_client.query_order(order_no)
        if profiles:
            break
        await asyncio.sleep(2)  # Ждем 2 секунды между попытками

    if not profiles:
        await callback.message.edit_text(
            text=TEXTS["esim_not_ready"],
            reply_markup=get_back_to_main_keyboard()
        )
        await state.clear()
        return

    # Берем первый профиль из заказа
    profile = profiles[0]

    # Формируем информацию о профиле
    ac = profile.get("ac", "")  # Activation Code
    qr_code_url = profile.get("qrCodeUrl", "")
    iccid = profile.get("iccid", "")

    esim_details = TEXTS["esim_details"].format(
        iccid=iccid,
        ac=ac,
        qr_code_url=qr_code_url
    )

    # Отправляем детали eSIM
    await callback.message.edit_text(
        text=esim_details,
        reply_markup=get_back_to_main_keyboard(),
        disable_web_page_preview=False  # Показываем QR-код, если URL указывает на изображение
    )

    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data == "cancel_purchase")
async def cancel_purchase(callback: CallbackQuery, state: FSMContext):
    """Отмена покупки"""
    await callback.message.edit_text(
        text=TEXTS["operation_cancelled"],
        reply_markup=get_back_to_main_keyboard()
    )
    await state.clear()
    await callback.answer()


# Обработчик ввода страны текстом
@router.message(BuyingStates.selecting_country)
async def process_country_text(message: Message, state: FSMContext):
    """Обработка ввода названия страны текстом"""
    country_name = message.text.strip().capitalize()

    # Проверяем, есть ли код страны
    if country_name in COUNTRY_CODES:
        country_code = COUNTRY_CODES[country_name]

        # Сохраняем информацию о стране
        await state.update_data(
            country_name=country_name,
            country_code=country_code
        )

        # Отправляем сообщение о загрузке
        loading_message = await message.answer(
            text=TEXTS["loading_packages"].format(country_name=country_name)
        )

        # Получаем пакеты для выбранной страны
        packages = esim_client.get_packages_by_country(country_code)

        # Дедуплицируем пакеты
        packages = deduplicate_packages(packages)

        # Сохраняем пакеты в состоянии
        await state.update_data(packages=packages)

        if not packages:
            # Если пакеты не найдены
            no_packages_text = TEXTS["no_packages"].format(country_name=country_name)
            await loading_message.edit_text(
                text=no_packages_text,
                reply_markup=get_buy_esim_keyboard()
            )
            return

        # Отображаем тарифы
        packages_text = TEXTS["choose_package"].format(country_name=country_name)
        await loading_message.edit_text(
            text=packages_text,
            reply_markup=get_packages_keyboard(packages, country_code, country_name)
        )
        await state.set_state(BuyingStates.selecting_package)
    else:
        # Если код страны не найден
        await message.answer(
            text=TEXTS["nothing_found"],
            reply_markup=get_buy_esim_keyboard()
        )