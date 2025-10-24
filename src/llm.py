from typing import Dict, Any
from .yandex_api import generate_route_for_places


async def request_to_llm(user_data: dict) -> dict:
    # 1. Данные о локации
    location = user_data.get('location', '')
    interests = user_data.get('interests', '')

    # 2. Заглушка, ИИ Генерация маршрута на картах
    suggested_places = [
        "Нижегородский кремль, Нижний Новгород",
        "Чкаловская лестница, Нижний Новгород",
        "Улица Большая Покровская, Нижний Новгород"
    ]

    # 3. Создание карт
    static_map_url, interactive_map_url, coordinates = await generate_route_for_places(suggested_places)

    # ИИ
    # timeline = await real_ai_request(interests, suggested_places)

    # 5. заглушка ИИ
    timeline = [
        {"time": "10:00", "place": "Нижегородский кремль", "description": "Начало экскурсии", "duration": "1.5 ч"},
        {"time": "11:30", "place": "Чкаловская лестница", "description": "Прогулка и фото", "duration": "1 ч"},
        {"time": "12:30", "place": "Большая Покровская", "description": "Обед и шоппинг", "duration": "2 ч"}
    ]

    return {
        "success": True,
        "timeline": timeline,
        "static_map_url": static_map_url,
        "interactive_map_url": interactive_map_url,
        "coordinates": coordinates
    }


async def request():
    """Старая функция для обратной совместимости"""
    print("Ponyal, Prinyal")
    return await request_to_llm({})