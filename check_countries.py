# check_countries.py
# Скрипт для проверки соответствия названий стран в REGIONS и COUNTRY_CODES

from config import REGIONS, COUNTRY_CODES


def extract_country_names_from_regions():
    """Извлекает все названия стран из REGIONS без эмодзи"""
    all_countries = set()

    for region_key, region_data in REGIONS.items():
        # Основные страницы стран
        if "countries" in region_data:
            for country in region_data["countries"]:
                # Удаляем эмодзи (первый символ + пробел)
                if " " in country:
                    country_name = country.split(" ", 1)[1]
                    all_countries.add(country_name)

        # Дополнительные страницы
        for page_key in [f"countries_page{i}" for i in range(2, 6)]:
            if page_key in region_data:
                for country in region_data[page_key]:
                    if " " in country:
                        country_name = country.split(" ", 1)[1]
                        all_countries.add(country_name)

    return all_countries


def check_countries():
    """Проверяет соответствие названий стран"""
    region_countries = extract_country_names_from_regions()
    country_codes_keys = set(COUNTRY_CODES.keys())

    print("=== ПРОВЕРКА СООТВЕТСТВИЯ НАЗВАНИЙ СТРАН ===")
    print(f"Стран в REGIONS: {len(region_countries)}")
    print(f"Стран в COUNTRY_CODES: {len(country_codes_keys)}")
    print()

    # Страны в REGIONS, но не в COUNTRY_CODES
    missing_in_codes = region_countries - country_codes_keys
    if missing_in_codes:
        print("❌ СТРАНЫ В REGIONS, НО НЕТ В COUNTRY_CODES:")
        for country in sorted(missing_in_codes):
            print(f"  - {country}")
        print()

    # Страны в COUNTRY_CODES, но не в REGIONS
    missing_in_regions = country_codes_keys - region_countries
    if missing_in_regions:
        print("⚠️  СТРАНЫ В COUNTRY_CODES, НО НЕТ В REGIONS:")
        for country in sorted(missing_in_regions):
            print(f"  - {country}")
        print()

    # Успешные совпадения
    matching_countries = region_countries & country_codes_keys
    print(f"✅ УСПЕШНЫХ СОВПАДЕНИЙ: {len(matching_countries)}")

    if not missing_in_codes and not missing_in_regions:
        print("🎉 ВСЕ НАЗВАНИЯ СТРАН СООТВЕТСТВУЮТ!")

    return missing_in_codes, missing_in_regions


def show_all_region_countries():
    """Показывает все страны по регионам"""
    print("\n=== ВСЕ СТРАНЫ ПО РЕГИОНАМ ===")

    for region_key, region_data in REGIONS.items():
        print(f"\n🌍 {region_data['name']} ({region_key}):")

        # Основная страница
        if "countries" in region_data:
            print("  Страница 1:")
            for country in region_data["countries"]:
                if " " in country:
                    country_name = country.split(" ", 1)[1]
                    code = COUNTRY_CODES.get(country_name, "❌ НЕТ КОДА")
                    print(f"    {country} → {code}")

        # Дополнительные страницы
        for page_num in range(2, 6):
            page_key = f"countries_page{page_num}"
            if page_key in region_data:
                print(f"  Страница {page_num}:")
                for country in region_data[page_key]:
                    if " " in country:
                        country_name = country.split(" ", 1)[1]
                        code = COUNTRY_CODES.get(country_name, "❌ НЕТ КОДА")
                        print(f"    {country} → {code}")


if __name__ == "__main__":
    # Основная проверка
    missing_in_codes, missing_in_regions = check_countries()

    # Подробный вывод по регионам
    show_all_region_countries()

    print(f"\n=== РЕЗУЛЬТАТ ===")
    if not missing_in_codes and not missing_in_regions:
        print("✅ Конфигурация корректна! Все страны соответствуют.")
    else:
        print("❌ Есть несоответствия, требуется исправление.")