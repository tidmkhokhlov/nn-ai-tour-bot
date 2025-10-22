import json
from pathlib import Path

PHRASES_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "phrases.json"

with open(PHRASES_PATH, "r", encoding="utf-8") as f:
    PHRASES = json.load(f)

def get_phrase(section: str, key: str) -> str:
    phrases = PHRASES.get(section, {}).get(key, [])
    if not phrases:
        return "🤖 Ошибка: фраза не найдена."
    return phrases[0]
