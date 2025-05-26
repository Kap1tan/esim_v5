# utils/esim_client.py

import requests
import json
import logging
from typing import Dict, List, Optional, Any, Union
import uuid

# Настройка логирования
logger = logging.getLogger(__name__)


class ESIMAccessClient:
    """
    Класс для работы с API eSIM Access
    """

    def __init__(self, access_code: str):
        """
        Инициализация клиента API eSIM Access

        :param access_code: Access Code для API eSIM Access
        """
        self.base_url = "https://api.esimaccess.com/api/v1/open"
        self.headers = {
            "RT-AccessCode": access_code,
            "Content-Type": "application/json"
        }

    def _is_regional_package(self, package_name: str, country_code: str) -> bool:
        """
        Проверяет, является ли пакет региональным (не для конкретной страны)

        :param package_name: Название пакета
        :param country_code: Код страны
        :return: True, если пакет региональный
        """
        # Список ключевых слов для региональных пакетов
        regional_keywords = [
            "Global", "Asia", "Europe", "Africa", "Americas", "CIS", "Middle East",
            "Multi", "Regional", "World", "International", "Continental",
            "areas", "countries", "regions"
        ]

        # Проверяем название пакета
        package_name_lower = package_name.lower()
        for keyword in regional_keywords:
            if keyword.lower() in package_name_lower:
                return True

        # Если пакет содержит код страны в названии, он не региональный
        if country_code.lower() in package_name_lower:
            return False

        return False

    def _is_daily_package(self, package: Dict[str, Any]) -> bool:
        """
        Проверяет, является ли пакет посуточным

        :param package: Данные пакета
        :return: True, если пакет посуточный
        """
        duration_unit = package.get("durationUnit", "").upper()
        duration = package.get("duration", 0)
        data_type = package.get("dataType", 1)

        # Посуточные пакеты: dataType = 2 (daily reset) или короткий период с DAY
        return data_type == 2 or (duration_unit == "DAY" and duration <= 7)

    def get_packages_by_country(self, country_code: str) -> List[Dict[str, Any]]:
        """
        Получение тарифов для конкретной страны с фильтрацией региональных пакетов

        :param country_code: Код страны (ISO)
        :return: Список доступных пакетов (только для конкретной страны)
        """
        endpoint = f"{self.base_url}/package/list"
        payload = {
            "locationCode": country_code,
            "type": "",
            "packageCode": "",
            "slug": "",
            "iccid": ""
        }

        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                all_packages = result.get("obj", {}).get("packageList", [])

                # Фильтруем только пакеты для конкретной страны
                country_packages = []
                for package in all_packages:
                    package_name = package.get("name", "")

                    # Пропускаем региональные пакеты
                    if self._is_regional_package(package_name, country_code):
                        continue

                    # Добавляем пакет в список
                    country_packages.append(package)

                # Сортируем: сначала посуточные, потом остальные
                country_packages.sort(key=lambda x: (
                    not self._is_daily_package(x),  # Посуточные первыми (False < True)
                    x.get("duration", 0),  # По возрастанию длительности
                    x.get("volume", 0)  # По возрастанию объема
                ))

                return country_packages
            else:
                logger.error(f"Ошибка API: {result.get('errorMsg')}")
                return []
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return []

    def order_profile(self, package_code: str, price: float, count: int = 1, period_num: Optional[int] = None) -> \
    Optional[str]:
        """
        Заказ eSIM профиля

        :param package_code: Код пакета
        :param price: Цена пакета
        :param count: Количество
        :param period_num: Количество дней для ежедневного тарифа (опционально)
        :return: Номер заказа или None в случае ошибки
        """
        endpoint = f"{self.base_url}/esim/order"
        transaction_id = f"WWS-{uuid.uuid4().hex[:8]}"
        amount = price * count

        # Базовая информация о пакете
        package_info = {
            "packageCode": package_code,
            "count": count,
            "price": price
        }

        # Добавляем periodNum если указан (для ежедневных тарифов)
        if period_num is not None:
            package_info["periodNum"] = period_num
            logger.info(f"Ordering daily package with periodNum: {period_num} days")

        payload = {
            "transactionId": transaction_id,
            "amount": amount,
            "packageInfoList": [package_info]
        }

        try:
            logger.info(f"Ordering profile: {payload}")
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                order_no = result.get("obj", {}).get("orderNo")
                logger.info(f"Successfully created order: {order_no}")
                return order_no
            else:
                logger.error(f"Ошибка заказа: {result.get('errorMsg')} (код: {result.get('errorCode')})")
                return None
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return None

    def query_order(self, order_no: str) -> List[Dict[str, Any]]:
        """
        Запрос информации о заказе

        :param order_no: Номер заказа
        :return: Список eSIM профилей в заказе
        """
        endpoint = f"{self.base_url}/esim/query"
        payload = {
            "orderNo": order_no,
            "iccid": "",
            "pager": {
                "pageNum": 1,
                "pageSize": 10
            }
        }

        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                esim_list = result.get("obj", {}).get("esimList", [])
                logger.info(f"Found {len(esim_list)} eSIM profiles for order {order_no}")
                return esim_list
            else:
                logger.error(f"Ошибка запроса заказа: {result.get('errorMsg')} (код: {result.get('errorCode')})")
                return []
        except Exception as e:
            logger.error(f"Ошибка запроса: {e}")
            return []

    def cancel_profile(self, esim_tran_no: str = None, iccid: str = None) -> bool:
        """
        Отмена неактивированного профиля eSIM

        :param esim_tran_no: Номер транзакции eSIM (рекомендуется)
        :param iccid: ICCID профиля (альтернатива)
        :return: True если отмена успешна
        """
        endpoint = f"{self.base_url}/esim/cancel"

        payload = {}
        if esim_tran_no:
            payload["esimTranNo"] = esim_tran_no
        elif iccid:
            payload["iccid"] = iccid
        else:
            logger.error("Необходим esimTranNo или iccid для отмены профиля")
            return False

        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                logger.info("eSIM профиль успешно отменен")
                return True
            else:
                logger.error(f"Ошибка отмены профиля: {result.get('errorMsg')} (код: {result.get('errorCode')})")
                return False
        except Exception as e:
            logger.error(f"Ошибка запроса отмены: {e}")
            return False

    def suspend_profile(self, esim_tran_no: str = None, iccid: str = None) -> bool:
        """
        Приостановка профиля eSIM

        :param esim_tran_no: Номер транзакции eSIM (рекомендуется)
        :param iccid: ICCID профиля (альтернатива)
        :return: True если приостановка успешна
        """
        endpoint = f"{self.base_url}/esim/suspend"

        payload = {}
        if esim_tran_no:
            payload["esimTranNo"] = esim_tran_no
        elif iccid:
            payload["iccid"] = iccid
        else:
            logger.error("Необходим esimTranNo или iccid для приостановки профиля")
            return False

        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                logger.info("eSIM профиль успешно приостановлен")
                return True
            else:
                logger.error(f"Ошибка приостановки профиля: {result.get('errorMsg')} (код: {result.get('errorCode')})")
                return False
        except Exception as e:
            logger.error(f"Ошибка запроса приостановки: {e}")
            return False