# 🤖 Gorky Guide 

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)  
[![Aiogram](https://img.shields.io/badge/aiogram-3.x-green?logo=telegram&logoColor=white)](https://docs.aiogram.dev/)  
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-black?logo=openai&logoColor=white)](https://platform.openai.com/)  
[![Yandex API](https://img.shields.io/badge/Yandex%20API-Geocoder-red?logo=yandex&logoColor=white)](https://yandex.ru/dev/maps/geocoder/)  
[![2GIS API](https://img.shields.io/badge/2GIS%20API-Places-brightgreen?logo=2gis&logoColor=white)](https://dev.2gis.com/)  

---

## 🌍 Описание проекта  

**[Gorky Guide](https://t.me/NNAITourBot)** — это интеллектуальный Telegram-бот,  
который подбирает **персональные маршруты прогулок** с учётом ваших **интересов, времени и локации**.  

> 🧠 Основан на GPT и интегрирован с API **Yandex** и **2ГИС**  
> для поиска реальных мест и построения оптимальных прогулочных маршрутов.  

---

## 🚀 Запуск проекта локально  

### 1️⃣ Установите зависимости  
```bash
pip install -r requirements.txt
```

### 2️⃣ Создайте файл .env в корне проекта
```bash
BOT_TOKEN=your_telegram_bot_token
YANDEX_API_KEY=your_yandex_api_key
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
DGIS_API_KEY=your_2gis_api_key
```

### 3️⃣ Запуск
```bash
python -m src.main
```

