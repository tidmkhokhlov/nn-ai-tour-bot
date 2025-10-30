from __future__ import annotations
import os
from typing import List, Dict, Any, Optional, Tuple
import httpx


def _get_2gis_key() -> str:
    key = os.getenv("DGIS_API_KEY") or os.getenv("TWOGIS_API_KEY") or os.getenv("TWO_GIS_API_KEY")
    if not key:
        raise RuntimeError("2GIS API key not found. Set DGIS_API_KEY or TWOGIS_API_KEY in .env")
    return key


CITY_CENTER_NN: Tuple[float, float] = (56.326, 44.006)  # Нижний Новгород (lat, lon)


def _normalize_address(text: str) -> str:
    t = (text or "").strip()
    # Заменим дробь в номере дома на «к» (корпус): 25/12 -> 25 к 12
    import re as _re
    t = _re.sub(r"(\d+)\s*/\s*(\d+)", r"\1 к \2", t)
    return t


def geocode_address_2gis(address_text: str) -> Optional[Tuple[float, float]]:
    """Грубо геокодирует адрес через items по тексту, ограничивая городом."""
    key = _get_2gis_key()
    endpoint = "https://catalog.api.2gis.com/3.0/items"
    q = f"{_normalize_address(address_text)} Нижний Новгород"
    params: Dict[str, Any] = {
        "key": key,
        "q": q,
        "page_size": 5,
        "fields": "items.point,items.address_name",
        "sort": "distance",
        "location": f"{CITY_CENTER_NN[1]:.6f},{CITY_CENTER_NN[0]:.6f}",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json() or {}
    except Exception:
        return None
    try:
        raw_items = (data.get("result") or {}).get("items") or []
    except Exception:
        raw_items = []
    for it in raw_items:
        point = it.get("point") or {}
        if isinstance(point, dict) and "lat" in point and "lon" in point:
            return (float(point["lat"]), float(point["lon"]))
    return None


def resolve_origin_2gis(start_coords: Optional[Tuple[float, float]], start_address_text: Optional[str]) -> Tuple[float, float]:
    """Определяет точку старта: координаты → геокод адреса → центр Н. Новгорода."""
    if start_coords and isinstance(start_coords, tuple):
        return start_coords
    if start_address_text:
        geo = geocode_address_2gis(start_address_text)
        if geo:
            return geo
    return CITY_CENTER_NN


def search_places_2gis(
    interests: str,
    start_coords: Optional[Tuple[float, float]] = None,
    start_address_text: Optional[str] = None,
    limit: int = 8,
    radius_m: int = 8000,
) -> List[Dict[str, Any]]:
    """Ищет места в 2ГИС по интересам в пределах Нижнего Новгорода. При наличии адреса — геокодирует старт.
    Формат элемента: {name, address, coords:(lat,lon)|None, rubrics:[...], rating:float|None}
    """
    key = _get_2gis_key()
    endpoint = "https://catalog.api.2gis.com/3.0/items"
    base_q = (interests or "").strip() or "интересные места"
    lq = base_q.lower()
    # Простое расширение запросов под популярные интересы
    extra = []
    if "истор" in lq:
        extra += ["музей", "памятник", "кремль", "усадьба", "экскурсия"]
    if any(k in lq for k in ["еда", "ресторан", "кафе", "фуд", "кофе"]):
        extra += ["ресторан", "кафе", "кофейня"]
    if any(k in lq for k in ["кино", "театр", "клуб", "ночн"]):
        extra += ["кинотеатр", "театр", "клуб"]
    q = (base_q + " " + " ".join(extra)).strip()

    # Гео: координаты старта, иначе геокод адреса, иначе центр НН
    loc_lat, loc_lon = resolve_origin_2gis(start_coords, start_address_text)

    params: Dict[str, Any] = {
        "key": key,
        "q": f"{q} Нижний Новгород",
        "page_size": max(3, min(limit, 15)),
        "fields": "items.point,items.address_name,items.rubrics,items.rating,items.type",
        "sort": "distance",
        "location": f"{loc_lon:.6f},{loc_lat:.6f}",
        "radius": int(radius_m),
    }

    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json() or {}
    except Exception as e:
        raise RuntimeError(f"2GIS request failed: {type(e).__name__}")

    items = []
    try:
        raw_items = (data.get("result") or {}).get("items") or []
    except Exception:
        raw_items = []

    for it in raw_items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        address = it.get("address_name") or ""
        itype = it.get("type") or ""
        point = (it.get("point") or {})
        coords = None
        if isinstance(point, dict) and "lat" in point and "lon" in point:
            coords = (float(point["lat"]), float(point["lon"]))
        # фильтруем административные/гео-единицы
        if itype in {"adm_div", "street", "settlement", "district", "region"}:
            continue
        rubrics = []
        rbs = it.get("rubrics") or []
        if isinstance(rbs, list):
            for rb in rbs:
                title = (rb.get("name") or rb.get("title") or "").strip()
                if title:
                    rubrics.append(title)
        rating = None
        rt = it.get("rating")
        try:
            if isinstance(rt, dict) and rt.get("rating") is not None:
                rating = float(rt.get("rating"))
        except Exception:
            rating = None
        items.append({
            "name": name,
            "address": address,
            "coords": coords,
            "rubrics": rubrics,
            "rating": rating,
            "type": itype,
        })

    return items


def search_places_2gis_by_query(
    query: str,
    origin: Tuple[float, float],
    limit: int = 6,
    radius_m: int = 8000,
) -> List[Dict[str, Any]]:
    """Ищет места в 2ГИС по одному короткому запросу около origin в Н. Новгороде."""
    key = _get_2gis_key()
    endpoint = "https://catalog.api.2gis.com/3.0/items"
    loc_lat, loc_lon = origin
    q = f"{(query or '').strip()} Нижний Новгород"
    params: Dict[str, Any] = {
        "key": key,
        "q": q,
        "page_size": max(1, min(limit, 15)),
        "fields": "items.point,items.address_name,items.rubrics,items.rating,items.type",
        "sort": "distance",
        "location": f"{loc_lon:.6f},{loc_lat:.6f}",
        "radius": int(radius_m),
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            r = client.get(endpoint, params=params)
            r.raise_for_status()
            data = r.json() or {}
    except Exception:
        return []
    items: List[Dict[str, Any]] = []
    raw_items = (data.get("result") or {}).get("items") or []
    for it in raw_items:
        name = (it.get("name") or "").strip()
        if not name:
            continue
        itype = it.get("type") or ""
        if itype in {"adm_div", "street", "settlement", "district", "region"}:
            continue
        address = it.get("address_name") or ""
        point = (it.get("point") or {})
        coords = None
        if isinstance(point, dict) and "lat" in point and "lon" in point:
            coords = (float(point["lat"]), float(point["lon"]))
        rubrics: List[str] = []
        rbs = it.get("rubrics") or []
        if isinstance(rbs, list):
            for rb in rbs:
                title = (rb.get("name") or rb.get("title") or "").strip()
                if title:
                    rubrics.append(title)
        rating = None
        rt = it.get("rating")
        try:
            if isinstance(rt, dict) and rt.get("rating") is not None:
                rating = float(rt.get("rating"))
        except Exception:
            rating = None
        items.append({
            "name": name,
            "address": address,
            "coords": coords,
            "rubrics": rubrics,
            "rating": rating,
            "type": itype,
        })
    return items


