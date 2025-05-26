# utils/currency.py

import requests
import logging
from typing import Optional
import time

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """Класс для конвертации валют с кэшированием"""

    def __init__(self):
        self.usd_to_rub_rate = 95.0  # Резервный курс на случай проблем с API
        self._last_update = 0
        self._cache_duration = 300  # Кэш на 5 минут

    def get_usd_to_rub_rate(self) -> float:
        """
        Получение текущего курса USD к RUB с кэшированием
        """
        current_time = time.time()

        # Если кэш еще актуален, возвращаем сохраненный курс
        if current_time - self._last_update < self._cache_duration:
            logger.info(f"Используется кэшированный курс: {self.usd_to_rub_rate}")
            return self.usd_to_rub_rate

        try:
            # Пробуем получить курс с Rapira API (как указано в требованиях)
            url = "https://api.rapira.net/open/market/rates"
            response = requests.get(url, timeout=5)
            logger.info(f"Rapira API ответ: статус {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Rapira API данные тип: {type(data)}")

                # Обрабатываем как dict (новый формат API)
                if isinstance(data, dict):
                    # Проверяем разные возможные структуры
                    if "USDT/RUB" in data:
                        rate_data = data["USDT/RUB"]
                        if isinstance(rate_data, dict) and "high" in rate_data:
                            high_rate = rate_data["high"]
                            if high_rate:
                                self.usd_to_rub_rate = float(high_rate)
                                self._last_update = current_time
                                logger.info(f"Получен курс USDT/RUB HIGH с Rapira (dict): {self.usd_to_rub_rate}")
                                return self.usd_to_rub_rate

                    # Если это другая структура dict, ищем по ключам
                    for key, value in data.items():
                        if "USDT" in key and "RUB" in key and isinstance(value, dict):
                            high_rate = value.get("high")
                            if high_rate:
                                self.usd_to_rub_rate = float(high_rate)
                                self._last_update = current_time
                                logger.info(f"Получен курс {key} HIGH с Rapira: {self.usd_to_rub_rate}")
                                return self.usd_to_rub_rate

                # Обрабатываем как list (старый формат API)
                elif isinstance(data, list):
                    for rate in data:
                        if isinstance(rate, dict) and rate.get("symbol") == "USDT/RUB":
                            high_rate = rate.get("high")
                            if high_rate:
                                self.usd_to_rub_rate = float(high_rate)
                                self._last_update = current_time
                                logger.info(f"Получен курс USDT/RUB HIGH с Rapira (list): {self.usd_to_rub_rate}")
                                return self.usd_to_rub_rate

                logger.warning(
                    f"Не найден курс USDT/RUB в ответе Rapira API. Структура: {list(data.keys()) if isinstance(data, dict) else 'list'}")

        except Exception as e:
            logger.warning(f"Ошибка получения курса с Rapira API: {e}")

        # Резервный вариант - ЦБ РФ
        try:
            url = "https://www.cbr-xml-daily.ru/daily_json.js"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                usd_rate = data["Valute"]["USD"]["Value"]
                self.usd_to_rub_rate = float(usd_rate)
                self._last_update = current_time
                logger.info(f"Получен курс USD/RUB с ЦБ РФ: {self.usd_to_rub_rate}")
                return self.usd_to_rub_rate
        except Exception as e:
            logger.warning(f"Ошибка получения курса с ЦБ РФ: {e}")

        # Если все API недоступны, используем резервный курс
        if current_time - self._last_update > self._cache_duration:
            logger.warning(f"Используется резервный курс USD/RUB: {self.usd_to_rub_rate}")
            self._last_update = current_time

        return self.usd_to_rub_rate

    def calculate_esim_price(self, usd_price: float) -> int:
        """
        Расчет цены eSIM по формуле заказчика:
        (Стоимость симки * курс рапиры USDT/RUB значение HIGH * 4) + 6.5%

        :param usd_price: Цена в долларах США
        :return: Цена в рублях (округленная)
        """
        rapira_rate = self.get_usd_to_rub_rate()

        # Формула: (Стоимость симки * курс рапиры USDT/RUB значение HIGH * 4) + 6.5%
        step1 = usd_price * rapira_rate * 4  # Умножаем на курс и на 4
        step2 = step1 * 1.065  # Добавляем 6.5%
        final_price = round(step2 / 10) * 10  # Округляем до 10 рублей

        logger.info(
            f"Расчет цены: ${usd_price} * {rapira_rate} (курс) * 4 = {step1:.2f}₽, +6.5% = {step2:.2f}₽, округлено = {final_price}₽")

        return int(final_price)

    def format_price_rub(self, usd_price: float) -> str:
        """
        Форматирование цены в рублях

        :param usd_price: Цена в долларах
        :return: Отформатированная цена в рублях
        """
        rub_price = self.calculate_esim_price(usd_price)
        return f"{rub_price}"


# Глобальный экземпляр конвертера
currency_converter = CurrencyConverter()