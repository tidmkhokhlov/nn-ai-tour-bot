import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"

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
        pos = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
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
        geo_object = data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
        address = geo_object["metaDataProperty"]["GeocoderMetaData"]["text"]
        return address
    except (KeyError, IndexError, ValueError):
        return None

def get_map(places: list[tuple[float, float]]) -> str:
    if not places:
        return "https://yandex.ru/maps"  # fallback, если координат нет
    points = [f"{lon},{lat}" for lat, lon in places]
    points_str = "~".join(points)
    yandex_url = f"https://yandex.ru/maps/?pt={points_str}&z=13&l=map"
    return yandex_url


def get_map_route(places: list[tuple[float, float]]) -> str:
    """
    Генерирует ссылку на Яндекс.Карты с маршрутом через все точки.
    Места подписаны номерами (1, 2, 3…).
    """
    if not places:
        return "https://yandex.ru/maps"  # fallback

    points_with_labels = []
    for idx, (lat, lon) in enumerate(places, start=1):
        # Формат: lon,lat,метка с номером
        points_with_labels.append(f"{lon},{lat},pm2dgl{idx}")
        # pm2dglN — стандартная метка Яндекс.Карт с номером N

    points_str = "~".join(points_with_labels)

    if len(places) < 3:
        # Меньше 3 мест — просто метки
        return f"https://yandex.ru/maps/?pt={points_str}&z=13&l=map"

    # 3 и больше — строим маршрут
    return f"https://yandex.ru/maps/?rtext={points_str}&rtt=mt&z=13&l=map"
