import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)

from src.bot.states.main_states import MainForm
from src.llm import request

router = Router()

# /start
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет 👋\nДавайте подберём прогулку!\n\n1️⃣ Напиши свои интересы (например: история, стрит-арт, кофейни)"
    )
    await state.set_state(MainForm.INTERESTS)


# Шаг 1 — интересы
@router.message(MainForm.INTERESTS)
async def process_interests(message: Message, state: FSMContext):
    await state.update_data(interests=message.text)
    await message.answer("⏰ Сколько у вас есть свободного времени на прогулку? (в часах)")
    await state.set_state(MainForm.TIME)


# Шаг 2 — время
@router.message(MainForm.TIME)
async def process_time(message: Message, state: FSMContext):
    await state.update_data(time=message.text)

    # Кнопка для отправки локации
    location_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        "📍 Отправьте своё текущее местоположение или введите адрес вручную:",
        reply_markup=location_keyboard
    )
    await state.set_state(MainForm.LOCATION)


# Шаг 3 — локация (обработка координат или текста)
@router.message(MainForm.LOCATION, F.location)
async def process_location_geo(message: Message, state: FSMContext):
    loc = message.location
    coords = f"{loc.latitude}, {loc.longitude}"
    await state.update_data(location=coords)

    data = await state.get_data()
    await send_summary(message, data)


@router.message(MainForm.LOCATION)
async def process_location_text(message: Message, state: FSMContext):
    await state.update_data(location=message.text)
    data = await state.get_data()
    await send_summary(message, data)


# Итог
async def send_summary(message: Message, data: dict):
    interests = data.get("interests")
    time = data.get("time")
    location = data.get("location")

    request()

    await message.answer(
        f"✅ Спасибо! Вот ваши данные:\n\n"
        f"✨ Интересы: {interests}\n"
        f"⏰ Время на прогулку: {time} часов\n"
        f"📍 Местоположение: {location}",
        reply_markup=ReplyKeyboardRemove()
    )



