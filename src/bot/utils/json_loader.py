import json
from pathlib import Path

PHRASES_PATH = Path(__file__).resolve().parents[3] / "data" / "content" / "phrases.json"

with open(PHRASES_PATH, "r", encoding="utf-8") as f:
    PHRASES = json.load(f)


def get_phrase_data(section: str, key: str, message: str = "message") -> str:
    section_data = PHRASES.get(section, {})

    if not section_data:
        return "🤖 Ошибка: фраза не найдена."

    if key in section_data:
        phrase_data = section_data[key]
        if isinstance(phrase_data, dict):
            return phrase_data.get(message, "🤖 Ошибка: фраза не найдена.")
        elif isinstance(phrase_data, str):
            return phrase_data

    return "🤖 Ошибка: фраза не найдена."

def get_button_text(section: str, key: str) -> str:
    section_data = PHRASES.get(section, {})

    if not section_data:
        return "🤖 Ошибка: фраза не найдена."

    if key in section_data:
        return section_data[key]

    return "🤖 Ошибка: фраза не найдена."

