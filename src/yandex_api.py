import aiohttp
import os
import urllib.parse
from typing import List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
# ВРЕМЕННО: добавляем ключ прямо в код для теста
YANDEX_API_KEY = "eaf721dd-abbc-48a2-b53e-a045e333186e"
# YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")  # закомментируйте эту строку
STATIC_API_KEY = "eaf721dd-abbc-48a2-b53e-a045e333186e"

GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"


# Геокодинг функции (оставляем как было)
async def get_coordinates(address: str) -> tuple[float, float] | None:
    params = {
        "apikey": YANDEX_API_KEY,
        "geocode": address,
        "format": "json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(GEOCODER_URL, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    try:
        pos = (data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"])
        lon, lat = map(float, pos.split())
        return lat, lon
    except (KeyError, IndexError, ValueError):
        return None


async def get_address(lat: float, lon: float) -> str | None:
    params = {
        "apikey": YANDEX_API_KEY,
        "geocode": f"{lon},{lat}",
        "format": "json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(GEOCODER_URL, params=params) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    try:
        address = (
            data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["metaDataProperty"][
                "GeocoderMetaData"]["text"]
        )
        return address
    except (KeyError, IndexError, ValueError):
        return None


# НОВАЯ ФУНКЦИЯ - Static API
async def create_static_map(points: List[Tuple[float, float]]) -> str:
    """
    Создает статичное изображение карты с метками точек через Static API
    """
    if len(points) < 1:
        raise ValueError("Нужна минимум 1 точка для отображения на карте")

    # Формируем метки для точек
    markers = []
    for i, (lat, lon) in enumerate(points):
        marker_type = "rdl" if i == 0 else "blm" if i == len(points) - 1 else "grm"
        markers.append(f"{lon},{lat},pm2{marker_type}{i + 1}")

    markers_str = "~".join(markers)

    # Параметры для Static API
    params = {
        "l": "map",
        "pt": markers_str,
        "size": "600,400",
        "apikey": STATIC_API_KEY or YANDEX_API_KEY  # Пробуем оба ключа
    }

    url = f"https://static-maps.yandex.ru/v1?{urllib.parse.urlencode(params)}"
    return url


# Функция для интерактивной карты (бесплатная, не требует ключа)
async def create_interactive_map_link(points: List[Tuple[float, float]]) -> str:
    """
    Создает ссылку на интерактивные Яндекс.Карты с отмеченными точками
    """
    if len(points) < 1:
        raise ValueError("Нужна минимум 1 точка для отображения на карте")

    points_str = "~".join([f"{lon},{lat}" for lat, lon in points])
    url = f"https://yandex.ru/maps/?pt={points_str}&z=13&l=map"
    return url


# Основная функция для генерации маршрута
async def generate_route_for_places(place_names: List[str]) -> Tuple[str, str, List[Tuple[float, float]]]:
    """
    Генерирует карты по списку названий мест
    """
    coordinates = []

    # Получаем координаты для каждого места через геокодер
    for place in place_names:
        coords = await get_coordinates(place)
        if coords:
            coordinates.append(coords)
            print(f"✅ Найдены координаты для: {place}")
        else:
            print(f"❌ Не удалось найти координаты для: {place}")

    if len(coordinates) < 1:
        raise ValueError("Не удалось получить координаты ни для одного места")

    # Создаем оба типа карт
    static_map_url = await create_static_map(coordinates)
    interactive_map_url = await create_interactive_map_link(coordinates)

    return static_map_url, interactive_map_url, coordinates