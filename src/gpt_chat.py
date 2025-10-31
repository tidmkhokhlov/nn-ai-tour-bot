from typing import List, Dict, Any
import re
import os
from .client import get_client, get_model, get_system_prompt
from .state import store, ChatMessage
from .twogis import resolve_origin_2gis, search_places_2gis_by_query

MAX_INPUT_CHARS = 6000
MAX_OUTPUT_TOKENS_CHAT = 512
MAX_OUTPUT_TOKENS_ROUTE = 900
ASSISTED_RAG_ENABLED = os.getenv("ASSISTED_RAG_ENABLED", "1").lower() in ("1", "true", "yes")


def _truncate(s: str, limit: int) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit]
def build_messages(user_id: int, user_text: str) -> List[ChatMessage]:
    """Строим массив сообщений для Chat Completions с учётом истории."""
    system_msg: ChatMessage = {
        "role": "system",
        "content": get_system_prompt(),
    }
    history = store.get(user_id)
    new_user_msg: ChatMessage = {"role": "user", "content": _truncate(user_text, MAX_INPUT_CHARS)}

    # финальный список: system (1 раз), затем предыдущая история, затем новое сообщение
    messages: List[ChatMessage] = [system_msg] + history + [new_user_msg]
    return messages

def chat_reply(user_id: int, user_text: str, model: str | None = None) -> str:
    """Делает запрос в Chat Completions, обновляет историю и возвращает текст ответа."""
    client = get_client()
    model_name = model or get_model()
    messages = build_messages(user_id, user_text)

    resp = client.chat.completions.create(
        model=model_name,
        messages=messages,  # type: ignore[arg-type]
        temperature=0,
        max_tokens=MAX_OUTPUT_TOKENS_CHAT,
    )
    answer = resp.choices[0].message.content or ""

    # Обновляем историю: добавляем текущую user-реплику и ответ ассистента
    updated_history: List[ChatMessage] = store.get(user_id) + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": answer},
    ]
    store.set(user_id, updated_history)
    return answer

def reset_history(user_id: int) -> None:
    store.reset(user_id)


def _build_base_route_prompt(data) -> str:
    interests = _truncate((data.get("interests") or "").strip(), MAX_INPUT_CHARS // 3)
    time_hours = float(data.get("time"))
    location_text = _truncate((data.get("location") or "").strip(), MAX_INPUT_CHARS // 3)
    coords = data.get("location_coords")
    start_point = location_text
    if not start_point and coords:
        lat, lon = coords
        start_point = f"{lat:.6f},{lon:.6f}"
    return (
        "Ты выступаешь как локальный гид по Нижнему Новгороду. Составь персональный план прогулки.\n"
        "Только чистый текст (никаких *, _, #, `, формул, без разметки). Для каждого пункта используй один уместный эмодзи: ставь его сразу после описания места, без дополнительных смайликов.\n\n"
        "Требования:\n"
        "- 3–5 реальных мест по интересам пользователя;\n"
        "- для каждого места дай увлекательное объяснение выбора без фразы 'почему туда';\n"
        "- предложи последовательный маршрут и таймлайн между этими объектами;\n"
        "- укажи примерное время на месте и примерное время перехода;\n"
        "- минимизируй лишние переходы и учитывай логику пути.\n\n"
        "Формат ответа:\n"
        "Маршрут на X часов\n"
        "Старт: <описание точки старта>\n"
        "1) Название — краткое пояснение; адрес/ориентир. Время на месте (мин). Переход (мин).\n"
        "2) ...\n"
        "Итого: суммарное время (мин) и примерная длина (км).\n"
        "Советы: 2–3 практичных совета (коротко).\n\n"
        f"Интересы пользователя: {interests or 'общие'}\n"
        f"Доступное время: {time_hours} часов\n"
        f"Стартовая точка: {start_point or 'центр города / популярная локация'}\n"
        "Включай места по заявленным интересам; если интересы — еда/кафе/рестораны, подбери преимущественно места, где можно поесть."
    )


def _build_catalog_appendix(candidates_text: str) -> str:
    return candidates_text  # больше не используется, оставлено для совместимости


def _is_low_quality_route(text: str) -> bool:
    s = (text or "").strip()
    if len(s) < 200:
        return True
    lowered = s.lower()
    bad_markers = [
        "не могу", "не знаю", "нет данных", "извин", "к сожалению",
        "я не имею", "как модель", "не удалось", "данные недоступны",
    ]
    if any(m in lowered for m in bad_markers):
        return True
    # Должно быть хотя бы 3 шага маршрута
    steps = re.findall(r"\n\s*(?:\d+\)|\d+\.|•|-\s)\s", s)
    if len(steps) < 3:
        return True
    return False


def _format_itinerary_from_2gis(places: List[Dict[str, Any]], time_hours: float, start_coords: tuple[float, float] | None, start_label: str | None = None, debug_info: List[str] | None = None) -> str:
    """Формирует текстовый маршрут из списка мест 2ГИС."""
    from math import radians, sin, cos, asin, sqrt

    walk_speed_kmh = 4.5
    remain_min = int(round(time_hours * 60)) + 30  # Буфер ±30 минут
    total_walk_min = 0
    total_stay_min = 0
    lines: List[str] = []

    lines.append(f"Маршрут на {time_hours:g} часов")
    if start_label:
        lines.append(f"Старт: {start_label}")
    else:
        lines.append("Старт: текущая локация пользователя" if start_coords else "Старт: центр города")

    def travel_time(a: tuple[float, float], b: tuple[float, float]) -> tuple[int, str, float]:
        """Возвращает (время_минут, способ_передвижения, расстояние_км)"""
        lat1, lon1 = a
        lat2, lon2 = b
        R = 6371.0
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        dphi = radians(lat2 - lat1)
        dlambda = radians(lon2 - lon1)
        x = sin(dphi/2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda/2) ** 2
        km = 2 * R * asin(sqrt(x))
        
        if km > 100.0:
            return 0, "ошибка", 0.0
        
        if km > 2.0:
            travel_min = int(round((km / 15.0) * 60)) + 10
            travel_min = min(travel_min, 60)  # Макс. 60 минут на транспорт
            return travel_min, "транспорт", km
        else:
            walk_min = int(round((km / walk_speed_kmh) * 60))
            return walk_min, "пешком", km

    prev = start_coords
    step = 1
    skipped = []
    places_added = 0
    total_distance_km = 0.0
    
    for p in places:
        name = p.get("name") or "Место"
        address = p.get("address") or "адрес не указан"
        coords = p.get("coords")  # (lat, lon) | None
        rubrics_list = p.get("rubrics") or []
        if isinstance(rubrics_list, list):
            rubrics = ", ".join([r for r in rubrics_list if isinstance(r, str) and r])
        else:
            rubrics = str(rubrics_list)
        rating = p.get("rating")
        reason = p.get("gpt_reason")
        if not reason:
            why_parts = []
            if rubrics:
                why_parts.append(rubrics)
            if rating:
                try:
                    why_parts.append(f"рейтинг {float(rating):.1f}")
                except Exception:
                    pass
            reason = "; ".join(why_parts) or "популярное место рядом по вашим интересам"

        if prev and coords:
            travel_min, method, distance_km = travel_time(prev, coords)
            if method == "ошибка":
                skipped.append(f"{name} (некорректные координаты)")
                if debug_info is not None:
                    debug_info.append(f"   ⏭️ Пропущено: {name} - некорректные координаты")
                continue
        else:
            travel_min, method, distance_km = 0, "старт", 0.0
        
        stay_min = p.get("gpt_time", 30)
        total_needed = travel_min + stay_min
        
        if places_added >= 3 and remain_min < total_needed:
            skipped.append(f"{name} (нужно {total_needed} мин, осталось {remain_min} мин, переход {travel_min} мин {method})")
            if debug_info is not None:
                debug_info.append(f"   ⏭️ Пропущено: {name} - не хватает времени (нужно {total_needed}, осталось {remain_min})")
            continue
        
        remain_min -= total_needed
        total_walk_min += travel_min
        total_stay_min += stay_min
        total_distance_km += distance_km
        
        travel_desc = f"Переход {travel_min} мин{' (транспорт)' if method == 'транспорт' else ''}"

        reason_text = str(reason or "Интересное место по вашим запросам").strip()
        # Забираем один эмодзи в конец, учитывая составные флаги (две литеры)
        emoji_match = re.search(r"((?:[\U0001F1E6-\U0001F1FF]{2})|[\U0001F000-\U0001FFFF])\s*$", reason_text)
        if emoji_match:
            emoji = emoji_match.group(1)
            reason_text = reason_text[:emoji_match.start()].rstrip()
            emoji_sep = " "
        else:
            emoji = "⭐"
            emoji_sep = ""
        reason_text = re.sub(r"[\U0001F000-\U0001FFFF]", "", reason_text).rstrip(",.; ")

        lines.append(
            f"{step}) {name} — {reason_text}{emoji_sep}{emoji}\n"
            f"Адрес: {address}\n"
            f"Время на месте: {stay_min} мин\n"
            f"Переход: {travel_desc}"
        )
        prev = coords or prev
        step += 1
        places_added += 1

    total_min = total_walk_min + total_stay_min
    total_km = round(total_distance_km, 1)
    lines.append(f"Итого: ~{total_min} мин, ~{total_km} км")
    lines.append("Советы: надевайте удобную обувь; уточняйте часы работы по месту; учитывайте время на транспорт.")
    
    if debug_info is not None:
        if skipped:
            debug_info.append(f"\n⚠️ Пропущено мест: {len(skipped)}")
            for s in skipped:
                debug_info.append(f"   {s}")
        debug_info.append(f"\n✅ В маршрут вошло: {places_added} из {len(places)} мест")
    
    return "\n".join(lines)

def _gpt_explain_and_estimate_time(places: List[Dict[str, Any]], interests: str) -> tuple[List[str], List[int]]:
    """GPT объясняет выбор мест И определяет время на каждое место."""
    client = get_client()
    model_name = get_model()
    bullet_lines = []
    for idx, p in enumerate(places):
        nm = p.get("name") or "Место"
        rubrics = p.get("rubrics")
        if isinstance(rubrics, list):
            rubrics_str = ", ".join([str(r) for r in rubrics if isinstance(r, str)])
        else:
            rubrics_str = str(rubrics or "")
        bullet_lines.append(f"{idx+1}. {nm} | рубрики: {rubrics_str}")
    
    user_prompt = (
        "Ниже список мест для маршрута. Интересы пользователя: "
        + (interests or "общие")
        + ".\n\nДля КАЖДОГО места:\n"
        "1. Напиши краткое объяснение (20-30 слов), почему вам туда стоит зайти (обращение на 'вы', без фразы 'почему туда')\n"
        "2. Оцени, сколько минут нужно провести в этом месте (от 15 до 60 минут)\n\n"
        "3. Используй один уместный эмодзи: поставь его сразу после пояснения, без дополнительных смайликов\n\n"
        "Примеры времени:\n"
        "- Памятник, скульптура: 10-15 минут\n"
        "- Музей небольшой: 30-40 минут\n"
        "- Музей большой (кремль, музей истории): 45-60 минут\n"
        "- Парк, набережная: 20-30 минут\n"
        "- Смотровая площадка: 15-20 минут\n\n"
        "ФОРМАТ ОТВЕТА (JSON):\n"
        "[\n"
        '  {"explanation": "текст объяснения", "minutes": 30},\n'
        '  {"explanation": "текст объяснения", "minutes": 45}\n'
        "]\n\n"
        "ВАЖНО:\n"
        "- Возвращай ТОЛЬКО JSON-массив\n"
        "- Ровно " + str(len(places)) + " элементов\n"
        "- Запрещены слова: 'может быть', 'будет интересно', 'любителям'\n"
        "- Активные формулировки: 'здесь вы увидите', 'вам откроется'\n\n"
        "Места:\n" + "\n".join(bullet_lines)
    )
    
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Ты помогаешь планировать маршруты. Возвращай ТОЛЬКО валидный JSON-массив с объяснениями и временем."},
                {"role": "user", "content": _truncate(user_prompt, MAX_INPUT_CHARS)},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        import json as _json
        content = (resp.choices[0].message.content or "").strip()
        # Убираем markdown если есть
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        
        data = _json.loads(content)
        
        if isinstance(data, list) and len(data) >= len(places):
            explanations = []
            times = []
            for i, item in enumerate(data[:len(places)]):
                if isinstance(item, dict):
                    expl = item.get("explanation", "Интересное место")
                    mins = item.get("minutes", 30)
                    # Валидация времени: от 10 до 60 минут
                    if not isinstance(mins, (int, float)) or mins < 10 or mins > 60:
                        mins = 30
                    explanations.append(str(expl))
                    times.append(int(mins))
                else:
                    explanations.append("Интересное место по вашим запросам")
                    times.append(30)
            
            return explanations, times
    except Exception:
        pass
    
    # Fallback: дефолтные объяснения и время
    explanations = ["Интересное место по вашим запросам"] * len(places)
    times = [30] * len(places)
    return explanations, times


def _apply_heuristic_rules(text_lower: str, result: Dict[str, List[str]]) -> None:
    """Применяет эвристические правила для классификации интересов."""
    from .categories_config import HEURISTIC_RULES
    
    for keywords, category, queries in HEURISTIC_RULES:
        if any(kw in text_lower for kw in keywords):
            if result[category]:
                result[category] = list(dict.fromkeys(result[category] + queries))
            else:
                result[category] = queries


def _classify_interests_to_queries(interests: str) -> Dict[str, List[str]]:
    """Классифицирует интересы пользователя в поисковые запросы для 2GIS."""
    from .categories_config import ALL_CATEGORIES, SYSTEM_PROMPT, FOOD_KEYWORDS, DEFAULT_CATEGORIES
    
    text = str(interests or "").strip()
    client = get_client()
    model_name = get_model()
    
    # Попытка классификации через GPT
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Интересы: {text}"},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        import json as _json
        content = resp.choices[0].message.content or "{}"
        data = _json.loads(content)
        
        if isinstance(data, dict):
            # Санитизация значений
            out: Dict[str, List[str]] = {}
            for k in ALL_CATEGORIES:
                vals = data.get(k) or []
                if isinstance(vals, list):
                    out[k] = [str(v)[:40] for v in vals if isinstance(v, (str, int, float))][:6]
                else:
                    out[k] = []
            return out
    except Exception:
        pass
    # Heuristic fallback
    l = text.lower()
    result: Dict[str, List[str]] = {cat: [] for cat in ALL_CATEGORIES}
    
    # Применяем правила из конфига
    _apply_heuristic_rules(l, result)
    
    # Специальные правила
    # 1. Военная техника (ТОЛЬКО если упоминается "военная" или "военный")
    if "военн" in l and ("техник" in l or "музей" in l or "оруж" in l):
        result["history"] = list(dict.fromkeys(result["history"] + ["музей военной техники", "военный музей"]))
    
    # 2. Архитектура XX века (требует упоминание "век")
    if any(x in l for x in ["архитектур", "конструктивизм", "модерн", "советск"]) and "век" in l:
        result["art"] = list(dict.fromkeys(result["art"] + ["архитектура XX века", "конструктивизм"]))
    
    # 3. Еда (НЕ добавляем если пользователь хочет гулять в парках)
    parks_hit = any(x in l for x in ["парк", "сквер", "сад", "лесопарк", "гуля", "прогул"])
    food_explicit = any(x in l for x in FOOD_KEYWORDS)
    
    if food_explicit and not parks_hit:
        result["food"] = ["ресторан", "кафе", "кофейня", "бар"]
    
    # 4. Дедупликация views (может накопиться много дубликатов)
    if result.get("views"):
        result["views"] = list(dict.fromkeys(result["views"]))
    
    # 5. Базовая страховка: если все пусто — дефолтные значения
    if not any(result.values()):
        result.update(DEFAULT_CATEGORIES)
    
    return result


def _dedupe_places(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        key = (it.get("name") or "").lower().strip() + "|" + (it.get("address") or "").lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _filter_unwanted_places(places: List[Dict[str, Any]], allow_food: bool) -> List[Dict[str, Any]]:
    """Фильтрует нежелательные места: еду (если не запрошена) и административные объекты."""
    filtered: List[Dict[str, Any]] = []
    
    food_keywords = ["ресто", "кафе", "кофе", "бар", "столовая", "бистро", "пицц", "суши", 
                     "бургер", "питан", "кулинар", "фастфуд", "закусочная", "буфет", "гриль"]
    
    # Административные/технические объекты, которые не интересны для прогулки
    admin_keywords = [
        # Административные учреждения
        "дирекци", "администрац", "управлен", "офис", "план-схем", "информационн", 
        "комната матери", "жилищно-коммунальн", "организац", "учрежден",
        
        # Финансовые и деловые
        "банк", "страхов", "нотариус", "юридическ", "суд", "библиотек",
        
        # Компании и корпорации (административные здания)
        "газпром", "роснефт", "сбербанк", "втб", "альфа-банк", "тинькофф",
        "мтс", "мегафон", "билайн", "ростелеком", "почта россии",
        
        # Служебные помещения
        "офисное здание", "бизнес-центр", "деловой центр", "административное здание",
        "служебное помещение", "управляющая компания", "диспетчерская",
        
        # Технические объекты
        "котельная", "трансформаторная", "подстанция", "тепловой пункт"
    ]
    
    for p in places:
        rub = ", ".join(p.get("rubrics", [])).lower()
        name = (p.get("name") or "").lower()
        
        # Фильтруем административные объекты
        is_admin = any(k in rub or k in name for k in admin_keywords)
        if is_admin:
            continue
        
        # Фильтруем еду, если не запрошена
        if not allow_food:
            is_food_place = any(k in rub or k in name for k in food_keywords)
            is_nature_place = any(k in rub or k in name for k in ["парк", "сквер", "сад", "набережн", 
                                                                    "бульвар", "лесопарк", "роща", "аллея", "променад"])
            
            # Если это ТОЛЬКО заведение питания (не парк с рестораном) — пропускаем
            if is_food_place and not is_nature_place:
                continue
        
        filtered.append(p)
    
    return filtered


def _build_interest_signals(interests_text: str) -> Dict[str, bool]:
    t = (interests_text or "").lower()
    return {
        "stroll": any(k in t for k in ["гуля", "прогул", "погуля", "фото-прогул", "walk"]),
        "food": any(k in t for k in ["еда", "ресто", "кафе", "кофе", "поесть", "вкусн", "бар", "кушать", "перекус"]),
        "history": "истор" in t,
        "art": any(k in t for k in ["искус", "галер", "арт", "выстав"]),
        "views": any(k in t for k in ["панора", "вид", "смотор", "набереж"]),
        "parks": any(k in t for k in ["парк", "сквер", "сад", "лесопарк"]),
        "entertainment": any(k in t for k in ["кино", "театр", "клуб", "концерт"]),
    }


def _place_distance_km(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if not a or not b:
        return 0.0
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    dphi = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    x = sin(dphi/2) ** 2 + cos(phi1) * cos(phi2) * sin(dl/2) ** 2
    return 2 * R * asin(sqrt(x))


def _gpt_select_best_places(places: List[Dict[str, Any]], interests: str, target_count: int = 5) -> List[Dict[str, Any]]:
    """GPT выбирает наиболее подходящие места из списка по интересам пользователя."""
    if len(places) <= target_count:
        return places
    
    client = get_client()
    model_name = get_model()
    
    # Формируем список мест для GPT
    items_text = []
    for idx, p in enumerate(places):
        nm = p.get("name") or "Место"
        rubrics = ", ".join(p.get("rubrics", [])) if isinstance(p.get("rubrics"), list) else ""
        rating = p.get("rating")
        rating_str = f" | рейтинг {rating:.1f}" if rating else ""
        items_text.append(f"{idx}: {nm} | {rubrics}{rating_str}")
    
    prompt = (
        f"Интересы пользователя: {interests}\n\n"
        f"Ниже список из {len(places)} мест в Нижнем Новгороде.\n"
        f"Выбери {target_count} САМЫХ ПОДХОДЯЩИХ мест для пешеходного маршрута.\n\n"
        "ВАЖНО:\n"
        "- Выбирай места, которые РЕАЛЬНО соответствуют интересам\n"
        "- Если интересы 'парки' — выбирай парки, а НЕ рестораны в парках\n"
        "- Если интересы 'кремль' — Нижегородский кремль должен быть в приоритете\n"
        "- НЕ выбирай административные здания (офисы Газпрома, банков, компаний)\n"
        "- НЕ выбирай технические объекты (подстанции, котельные, диспетчерские)\n"
        "- Учитывай рейтинг мест\n"
        "- СТАРАЙСЯ выбирать места, расположенные РЯДОМ друг с другом (компактный маршрут)\n"
        "- Избегай мест, которые находятся в разных концах города\n\n"
        f"Верни JSON-массив из {target_count} индексов (от 0 до {len(places)-1}) в порядке приоритета.\n"
        "Формат: [5, 12, 3, 8, 15]\n\n"
        "Места:\n" + "\n".join(items_text[:30])  # Ограничим для экономии токенов
    )
    
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Ты эксперт по туристическим маршрутам. Выбираешь наиболее подходящие места. Отвечай ТОЛЬКО JSON-массивом индексов."},
                {"role": "user", "content": _truncate(prompt, MAX_INPUT_CHARS)},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        import json as _json
        content = (resp.choices[0].message.content or "").strip()
        # Убираем markdown если есть
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        indices = _json.loads(content)
        if isinstance(indices, list) and all(isinstance(i, int) for i in indices):
            valid_indices = [i for i in indices if 0 <= i < len(places)][:target_count]
            if len(valid_indices) >= 3:  # Минимум 3 места
                return [places[i] for i in valid_indices]
    except Exception:
        pass
    
    # Fallback: берем первые target_count
    return places[:target_count]

def generate_route(data, model: str | None = None) -> tuple[str, list[tuple[float, float]]]:
    """Строит маршрут: места из 2ГИС + GPT выбирает лучшие."""
    interests = (data.get("interests") or "").strip()
    time_hours = float(data.get("time") or 2.0)
    location_text = (data.get("location") or "").strip()
    coords = data.get("location_coords")
    start_coords = coords if isinstance(coords, tuple) else None

    # 1) Классифицируем интересы в поисковые запросы
    cats = _classify_interests_to_queries(interests)
    origin = resolve_origin_2gis(start_coords, location_text if location_text else None)
    
    # 2) Собираем МНОГО мест из 2ГИС с разными радиусами
    pool: List[Dict[str, Any]] = []
    radii = [5000, 10000]  # 5км, 10км
    
    # Собираем все запросы из всех категорий
    from .categories_config import ALL_CATEGORIES
    
    all_queries: List[str] = []
    for cat in ALL_CATEGORIES:
        all_queries.extend(cats.get(cat) or [])
    
    # Если запросов мало, добавим общий поиск
    if not all_queries:
        all_queries = [interests]
    
    # Ищем с разными радиусами для большего охвата
    for radius in radii:
        for q in all_queries[:5]:  # Ограничим количество запросов
            pool.extend(search_places_2gis_by_query(q, origin=origin, limit=10, radius_m=radius))
    
    # Дедупликация
    candidates = _dedupe_places(pool)
    
    # Фильтруем нежелательные места
    signals = _build_interest_signals(interests)
    candidates_before_filter = len(candidates)
    candidates_filtered = _filter_unwanted_places(candidates, allow_food=signals.get("food", False))
    candidates_after_filter = len(candidates_filtered)
    
    # Для DEBUG
    alt_queries_used = []
    
    # Если после фильтрации осталось мало мест, переформулируем запрос и ищем еще
    if len(candidates_filtered) < 3:
        client = get_client()
        model_name = get_model()
        
        # Просим GPT придумать альтернативные запросы
        reformulate_prompt = (
            f"Интересы пользователя: {interests}\n\n"
            f"Мы искали места в Нижнем Новгороде по запросам: {all_queries[:5]}\n"
            f"Но нашли мало подходящих мест (административные объекты отфильтрованы).\n\n"
            f"Предложи 5-7 АЛЬТЕРНАТИВНЫХ поисковых запросов (1-3 слова) для поиска в 2ГИС.\n"
            f"Запросы должны быть:\n"
            f"- Связаны с интересами пользователя\n"
            f"- Конкретными (например: 'планетарий', 'научный музей', 'технопарк')\n"
            f"- НЕ административными (избегай: 'дирекция', 'управление', 'офис')\n\n"
            f"Верни JSON-массив строк: ['запрос1', 'запрос2', 'запрос3']"
        )
        
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Ты помогаешь находить альтернативные поисковые запросы. Отвечай ТОЛЬКО JSON-массивом строк."},
                    {"role": "user", "content": reformulate_prompt},
                ],
                temperature=0.7,
                max_tokens=200,
            )
            import json as _json
            content = (resp.choices[0].message.content or "").strip()
            # Убираем markdown
            if "```" in content:
                content = content.split("```")[1].replace("json", "").strip()
            
            alt_queries = _json.loads(content)
            
            if isinstance(alt_queries, list) and len(alt_queries) > 0:
                alt_queries_used = alt_queries[:7]
                
                # Ищем по альтернативным запросам с большим радиусом
                alt_pool: List[Dict[str, Any]] = []
                for q in alt_queries_used:
                    for radius in [10000, 20000]:  # 10км и 20км
                        alt_pool.extend(search_places_2gis_by_query(str(q), origin=origin, limit=12, radius_m=radius))
                
                # Объединяем и фильтруем
                if alt_pool:
                    pool.extend(alt_pool)
                    candidates = _dedupe_places(pool)
                    candidates_filtered = _filter_unwanted_places(candidates, allow_food=signals.get("food", False))
                    candidates_after_filter = len(candidates_filtered)
        except Exception:
            pass
    
    candidates = candidates_filtered
    
    if len(candidates) < 1:
        return "Не удалось найти достаточно мест по запросу. Уточните интересы или адрес."
    
    # 3) GPT выбирает лучшие 3-5 мест
    target = max(3, min(5, int(time_hours * 2)))
    shortlist = _gpt_select_best_places(candidates, interests, target_count=target)
    
    # 4) GPT объясняет выбор И определяет время на каждое место
    explanations, times = _gpt_explain_and_estimate_time(shortlist, interests)
    for i, p in enumerate(shortlist):
        if i < len(explanations):
            p["gpt_reason"] = explanations[i]
        if i < len(times):
            p["gpt_time"] = times[i]
    
    # DEBUG
    debug = os.getenv("DGIS_DEBUG", "0").lower() in ("1", "true", "yes")
    dbg_lines = [] if debug else None
    
    if debug:
        dbg_lines.append("\n\n" + "="*50)
        dbg_lines.append("=== DEBUG: Поиск мест ===")
        dbg_lines.append(f"Интересы пользователя: {interests}")
        dbg_lines.append(f"\nКлассификация интересов:")
        for cat, queries in cats.items():
            if queries:
                dbg_lines.append(f"  {cat}: {queries}")
        dbg_lines.append(f"\nВсе запросы к 2ГИС ({len(all_queries[:10])}): {all_queries[:10]}")
        dbg_lines.append(f"Радиусы поиска: {radii} метров")
        dbg_lines.append("")
        
        dbg_lines.append("=== Результаты от 2ГИС ===")
        dbg_lines.append(f"Всего найдено: {len(pool)} мест")
        dbg_lines.append(f"После дедупликации: {candidates_before_filter} мест")
        dbg_lines.append(f"После фильтрации нежелательных мест: {len(candidates)} мест")
        if candidates_after_filter < candidates_before_filter:
            dbg_lines.append(f"⚠️ Фильтр удалил {candidates_before_filter - candidates_after_filter} мест (административные, еда)")
        
        # Показываем если была переформулировка
        if alt_queries_used:
            dbg_lines.append(f"\n🔄 GPT переформулировал запрос:")
            dbg_lines.append(f"   Альтернативные запросы: {alt_queries_used}")
            dbg_lines.append(f"   Найдено дополнительно: {len(candidates) - candidates_after_filter} мест")
            dbg_lines.append(f"   Итого после переформулировки: {len(candidates)} мест")
        
        if len(candidates) > 0:
            dbg_lines.append(f"\nПервые 10 мест от 2ГИС:")
            for idx, it in enumerate(candidates[:10]):
                name = it.get('name', '?')
                rubrics = ', '.join(it.get('rubrics', []))
                rating = it.get('rating')
                rating_str = f" [{rating:.1f}★]" if rating else ""
                dbg_lines.append(f"  {idx+1}. {name}{rating_str}")
                dbg_lines.append(f"     Рубрики: {rubrics}")
        
        dbg_lines.append("")
        dbg_lines.append("=== Запрос к GPT для выбора мест ===")
        dbg_lines.append(f"Запросили у GPT выбрать {target} лучших мест из {len(candidates)}")
        
        dbg_lines.append("")
        dbg_lines.append(f"=== GPT выбрал {len(shortlist)} мест ===")
        for idx, it in enumerate(shortlist):
            name = it.get('name', '?')
            rubrics = ', '.join(it.get('rubrics', []))
            gpt_time = it.get('gpt_time', 30)
            dbg_lines.append(f"{idx+1}. {name} (время: {gpt_time} мин)")
            dbg_lines.append(f"   Рубрики: {rubrics}")
        
        dbg_lines.append("")
        dbg_lines.append("=== Формирование маршрута ===")
        dbg_lines.append(f"Доступно времени: {int(time_hours * 60)} минут")
    
    # 5) Формируем маршрут
    itinerary = _format_itinerary_from_2gis(shortlist, time_hours=time_hours, start_coords=origin, start_label=location_text or None, debug_info=dbg_lines)

    # 6) Собираем координаты
    coords_list: list[tuple[float, float]] = []
    for place in shortlist:
        c = place.get("coords")
        if c and isinstance(c, (list, tuple)) and len(c) == 2:
            coords_list.append((float(c[0]), float(c[1])))

    if debug and dbg_lines:
        dbg_lines.append("="*50)
        itinerary += "\n" + "\n".join(dbg_lines)
    
    return itinerary, coords_list


def generate_route_result(data, model: str | None = None) -> tuple[str, list[tuple[float, float]], bool]:
    """
    Возвращает (text, coords_list, ok).
    ok=False, если мест < 3 либо произошла ошибка подбора.
    """
    try:
        itinerary, coords_list = generate_route(data, model)
        if "Не удалось найти" in itinerary or len(coords_list) < 3:
            return (itinerary, coords_list, False)
        return (itinerary, coords_list, True)
    except Exception:
        return ("Не удалось сгенерировать маршрут. Попробуйте ещё раз позднее.", [], False)

