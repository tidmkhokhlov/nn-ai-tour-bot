from src.yandex_api import get_coordinates

def is_valid_time(time : str) -> bool:
    try:
        float(time.replace(',', '.'))
        return True
    except ValueError:
        return False

async def is_valid_location(location : str) -> bool:
    if location.startswith("Нижний Новгород"):
        pass
    elif location.startswith("Нижний"):
        location = location.replace("Нижний", "Нижний Новгород")
    elif location.startswith("НН"):
        location = location.replace("НН", "Нижний Новгород")
    elif location.startswith("НиНо"):
        location = location.replace("НиНо", "Нижний Новгород")
    else:
        location = "Нижний Новгород, " + location

    coords = await get_coordinates(location)
    return coords is not None