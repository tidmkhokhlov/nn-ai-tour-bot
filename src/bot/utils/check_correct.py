from src.yandex_api import get_coordinates

def is_valid_time(time : str) -> bool:
    try:
        float(time.replace(',', '.'))
        return True
    except ValueError:
        return False

async def is_valid_location(location : str) -> bool:
    coords = await get_coordinates(location)
    return coords is not None