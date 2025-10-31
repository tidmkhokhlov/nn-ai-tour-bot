import os
from dotenv import load_dotenv
from openai import OpenAI

# Подхватываем переменные окружения из .env (если есть)
load_dotenv()

def get_client() -> OpenAI:
    """Создаёт клиент OpenAI из переменной окружения OPENAI_API_KEY."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не найден. Укажите его в .env или окружении.")
    return OpenAI(api_key=api_key)

def get_model(default: str = "gpt-4o-mini") -> str:
    """Возвращает имя модели из OPENAI_MODEL или дефолт."""
    return os.getenv("OPENAI_MODEL", default)

