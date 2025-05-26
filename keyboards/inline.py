# keyboards/inline.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Any
from utils.currency import currency_converter


def get_start_keyboard():
    """Клавиатура для стартового меню"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Купить eSIM", callback_data="buy_esim"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
    )
    builder.row(
        InlineKeyboardButton(text="📱 Как установить eSIM", callback_data="setup"),
        InlineKeyboardButton(text="❓ Вопросы и ответы", callback_data="questions")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Зарабатывай с WorldWideSim", callback_data="partner")
    )

    return builder.as_markup()


def get_buy_esim_keyboard():
    """Клавиатура для выбора региона"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🐼 Азия", callback_data="region_asia")
    )
    builder.row(
        InlineKeyboardButton(text="🐪 Ближний восток", callback_data="region_middle_east")
    )
    builder.row(
        InlineKeyboardButton(text="🐌 Европа", callback_data="region_europe")
    )
    builder.row(
        InlineKeyboardButton(text="🦅 Америка", callback_data="region_americas")
    )
    builder.row(
        InlineKeyboardButton(text="🐻 СНГ", callback_data="region_cis")
    )
    builder.row(
        InlineKeyboardButton(text="🦁 Африка", callback_data="region_africa")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_countries_keyboard(region_key: str, countries: List[str], page: int = 1):
    """Клавиатура со странами для выбранного региона с пагинацией по 10 стран"""
    builder = InlineKeyboardBuilder()

    # Показываем 10 стран на странице
    countries_per_page = 10
    start_idx = (page - 1) * countries_per_page
    end_idx = start_idx + countries_per_page

    current_countries = countries[start_idx:end_idx]

    # Добавляем кнопки стран (каждая страна на отдельной строке)
    for country in current_countries:
        # Удаляем эмодзи из названия страны для callback_data
        if " " in country:
            country_name = country.split(" ", 1)[1]
        else:
            country_name = country

        builder.row(
            InlineKeyboardButton(text=country, callback_data=f"country_{country_name}")
        )

    # Добавляем навигацию если нужно
    total_pages = (len(countries) + countries_per_page - 1) // countries_per_page

    if total_pages > 1:
        nav_buttons = []

        # Левая кнопка
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="←", callback_data=f"page_{region_key}_{page - 1}")
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(text="−", callback_data="navigation_disabled")
            )

        # Средняя кнопка с номером страницы
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info")
        )

        # Правая кнопка
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="→", callback_data=f"page_{region_key}_{page + 1}")
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(text="−", callback_data="navigation_disabled")
            )

        builder.row(*nav_buttons)

    # Всегда возвращаемся к выбору регионов
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="buy_esim")
    )

    return builder.as_markup()


def is_daily_package(package: Dict[str, Any]) -> bool:
    """Определяет, является ли пакет ежедневным (посуточным)"""
    duration_unit = package.get("durationUnit", "").upper()
    duration = package.get("duration", 0)
    data_type = package.get("dataType", 1)

    # Ежедневные пакеты: dataType = 2 (daily reset) или короткий период с DAY
    return data_type == 2 or (duration_unit == "DAY" and duration <= 7)


def format_package_button_text(package: Dict[str, Any], country_name: str, usd_to_rub_rate: float) -> str:
    """Форматирует текст кнопки для пакета в рублях по формуле заказчика"""
    volume_bytes = package.get("volume", 0)
    duration = package.get("duration", 0)
    duration_unit = package.get("durationUnit", "DAY")
    price_usd = package.get("price", 0) / 10000  # Преобразование в доллары

    # Преобразование байтов в МБ или ГБ
    if volume_bytes >= 1073741824:  # 1 ГБ
        volume_str = f"{volume_bytes / 1073741824:.0f}ГБ"
    else:
        volume_str = f"{volume_bytes / 1048576:.0f}МБ"

    # Применяем формулу заказчика: (Стоимость симки * курс рапиры USDT/RUB значение HIGH * 4) + 6.5%
    step1 = price_usd * usd_to_rub_rate * 4  # Умножаем на курс и на 4
    step2 = step1 * 1.065  # Добавляем 6.5%
    rub_price = round(step2 / 10) * 10  # Округляем до 10 рублей

    # Проверяем тип пакета
    if is_daily_package(package):
        # Для ежедневных тарифов: "Страна 1ГБ/День — от 300₽"
        return f"{country_name} {volume_str}/День — от {int(rub_price)}₽"
    else:
        # Для обычных тарифов: "Страна 1ГБ, 7 дней — 500₽"
        if duration_unit == "DAY":
            duration_str = f"{duration} дней"
        elif duration_unit == "MONTH":
            duration_str = f"{duration} месяцев"
        else:
            duration_str = f"{duration} {duration_unit}"

        return f"{country_name} {volume_str}, {duration_str} — {int(rub_price)}₽"


def deduplicate_packages(packages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Убирает дублирующие пакеты с одинаковым объемом и продолжительностью, оставляя самый дешевый"""
    unique_packages = {}

    for package in packages:
        volume = package.get("volume", 0)
        duration = package.get("duration", 0)
        duration_unit = package.get("durationUnit", "DAY")
        data_type = package.get("dataType", 1)
        price = package.get("price", 0)

        # Создаем ключ для группировки одинаковых пакетов
        key = (volume, duration, duration_unit, data_type)

        # Если такого пакета еще нет или найден более дешевый
        if key not in unique_packages or price < unique_packages[key].get("price", float('inf')):
            unique_packages[key] = package

    return list(unique_packages.values())


def get_packages_keyboard(packages: List[Dict[str, Any]], country_code: str, country_name: str, page: int = 1):
    """Клавиатура с пакетами для выбранной страны с пагинацией и разделением типов"""
    builder = InlineKeyboardBuilder()

    # Дедуплицируем пакеты
    packages = deduplicate_packages(packages)

    # Получаем курс один раз для всех пакетов
    usd_to_rub_rate = currency_converter.get_usd_to_rub_rate()

    # Разделяем пакеты на ежедневные и обычные
    daily_packages = [p for p in packages if is_daily_package(p)]
    regular_packages = [p for p in packages if not is_daily_package(p)]

    # Сортируем каждую группу
    daily_packages.sort(key=lambda x: (x.get("volume", 0), x.get("price", 0)))
    regular_packages.sort(key=lambda x: (x.get("duration", 0), x.get("volume", 0), x.get("price", 0)))

    # Объединяем: сначала ежедневные, потом обычные
    all_packages = daily_packages + regular_packages

    # Показываем 10 пакетов на странице
    packages_per_page = 10
    start_idx = (page - 1) * packages_per_page
    end_idx = start_idx + packages_per_page

    current_packages = all_packages[start_idx:end_idx]

    # Определяем, нужен ли разделитель на текущей странице
    daily_count_on_page = 0
    regular_count_on_page = 0

    for i, package in enumerate(current_packages):
        actual_index = start_idx + i  # Реальный индекс в общем списке

        # Считаем типы пакетов на странице
        if is_daily_package(package):
            daily_count_on_page += 1
        else:
            regular_count_on_page += 1

        # Если это первый обычный пакет после ежедневных, добавляем разделитель
        if (daily_count_on_page > 0 and regular_count_on_page == 1 and
                not is_daily_package(package) and i > 0):
            builder.row(
                InlineKeyboardButton(text="──────────────────", callback_data="separator")
            )

        button_text = format_package_button_text(package, country_name, usd_to_rub_rate)
        builder.row(
            InlineKeyboardButton(text=button_text, callback_data=f"package_{actual_index}")
        )

    # Добавляем навигацию если нужно
    total_pages = (len(all_packages) + packages_per_page - 1) // packages_per_page

    if total_pages > 1:
        nav_buttons = []

        # Левая кнопка
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="←", callback_data=f"packages_page_{country_code}_{page - 1}")
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(text="−", callback_data="navigation_disabled")
            )

        # Средняя кнопка с номером страницы
        nav_buttons.append(
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info")
        )

        # Правая кнопка
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="→", callback_data=f"packages_page_{country_code}_{page + 1}")
            )
        else:
            nav_buttons.append(
                InlineKeyboardButton(text="−", callback_data="navigation_disabled")
            )

        builder.row(*nav_buttons)

    # Всегда возвращаемся к выбору регионов
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="buy_esim")
    )

    return builder.as_markup()


def get_days_selection_keyboard(package_index: int):
    """Клавиатура для выбора количества дней для ежедневного тарифа"""
    builder = InlineKeyboardBuilder()

    # Предлагаем популярные варианты дней
    days_options = [1, 3, 5, 7, 10, 15, 30]

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(days_options), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(days_options):
                days = days_options[i + j]
                day_text = f"{days} день" if days == 1 else f"{days} дней"
                row_buttons.append(
                    InlineKeyboardButton(
                        text=day_text,
                        callback_data=f"select_days_{package_index}_{days}"
                    )
                )
        builder.row(*row_buttons)

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(text="↩️ Назад к тарифам", callback_data="back_to_packages")
    )

    return builder.as_markup()


def get_confirm_keyboard(country_code: str):
    """Клавиатура для подтверждения покупки с СБП"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Оплатить по СБП", callback_data="pay_sbp")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data=f"back_to_packages_{country_code}")
    )

    return builder.as_markup()


def get_payment_done_keyboard():
    """Клавиатура после завершения платежа"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📱 Показать детали eSIM", callback_data="show_esim_details")
    )

    return builder.as_markup()


def get_back_to_countries_keyboard(region_data: str):
    """Клавиатура для возврата к выбору стран"""
    builder = InlineKeyboardBuilder()

    # Всегда возвращаемся к выбору регионов
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="buy_esim")
    )

    return builder.as_markup()


def get_profile_keyboard():
    """Клавиатура для профиля"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_setup_keyboard():
    """Клавиатура для установки eSIM"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_questions_keyboard():
    """Клавиатура для раздела вопросов"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Что такое eSIM?", callback_data="qa_what_is_esim")
    )
    builder.row(
        InlineKeyboardButton(text="Как подключить интернет?", callback_data="qa_how_to_connect")
    )
    builder.row(
        InlineKeyboardButton(text="Какой пакет мне выбрать?", callback_data="qa_which_package")
    )
    builder.row(
        InlineKeyboardButton(text="Можно ли звонить и писать SMS?", callback_data="qa_can_call_sms")
    )
    builder.row(
        InlineKeyboardButton(text="Мой телефон поддерживает eSIM?", callback_data="qa_phone_support")
    )
    builder.row(
        InlineKeyboardButton(text="Когда стартует тариф?", callback_data="qa_when_starts")
    )
    builder.row(
        InlineKeyboardButton(text="Как продлить eSIM?", callback_data="qa_how_extend")
    )
    builder.row(
        InlineKeyboardButton(text="Можно ли вернуть деньги?", callback_data="qa_refund")
    )
    builder.row(
        InlineKeyboardButton(text="Насколько безопасна eSIM?", callback_data="qa_is_safe")
    )
    builder.row(
        InlineKeyboardButton(text="Можно ли раздавать интернет?", callback_data="qa_share_internet")
    )
    builder.row(
        InlineKeyboardButton(text="Работают ли WhatsApp и Telegram?", callback_data="qa_messengers_work")
    )
    builder.row(
        InlineKeyboardButton(text="Чем eSIM лучше роуминга?", callback_data="qa_better_than_roaming")
    )
    builder.row(
        InlineKeyboardButton(text="Почему интернет бывает медленным?", callback_data="qa_slow_internet")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_qa_back_keyboard():
    """Клавиатура возврата к вопросам"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ К вопросам", callback_data="questions")
    )

    return builder.as_markup()


def get_back_to_main_keyboard():
    """Клавиатура возврата к главному меню"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_partner_keyboard():
    """Клавиатура для выбора типа партнерства"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Партнерская программа", callback_data="partner_referral")
    )
    builder.row(
        InlineKeyboardButton(text="Монетизировать сообщество", callback_data="partner_community")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="back_to_main")
    )

    return builder.as_markup()


def get_partner_referral_keyboard():
    """Клавиатура для партнерской программы"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📎 Поделиться с другом", callback_data="share_referral")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="partner")
    )

    return builder.as_markup()


def get_partner_community_keyboard():
    """Клавиатура для монетизации сообщества"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🛠 Получить партнёрского бота", url="https://t.me/levshurygin")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ В каталог", callback_data="partner")
    )

    return builder.as_markup()


def get_feedback_keyboard():
    """Клавиатура для обратной связи"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👍 Да", callback_data="feedback_yes"),
        InlineKeyboardButton(text="😕 Нет", callback_data="feedback_no")
    )

    return builder.as_markup()


def get_feedback_no_keyboard():
    """Клавиатура для отрицательной обратной связи"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="Ответы на частые вопросы", callback_data="questions")
    )
    builder.row(
        InlineKeyboardButton(text="Написать в поддержку", callback_data="support")
    )

    return builder.as_markup()