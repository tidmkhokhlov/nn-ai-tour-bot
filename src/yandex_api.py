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
        pos = (
            data["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
        )
        lon, lat = map(float, pos.split())
        return lat, lon
    except (KeyError, IndexError, ValueError):
        return None