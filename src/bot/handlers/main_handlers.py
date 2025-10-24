import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardRemove,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from src.bot.states.main_states import MainForm
from src.llm import request_to_llm
from src.bot.utils.check_correct import is_valid_time, is_valid_location
from src.bot.utils.correction import correction_location
from src.bot.utils.json_loader import get_phrase
import src.bot.keyboards.user_keyboards as ukb

router = Router()


# /start
@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        get_phrase("START", "FIRST_FEEL"),
        reply_markup=ukb.main_keyboard
    )
    await state.set_state(MainForm.INTERESTS)


# Повторный запуск через кнопку
@router.message(F.text == "Помоги пж с донашкой..")
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        get_phrase("START", "NEW_START"),
        reply_markup=ukb.main_keyboard
    )
    await state.set_state(MainForm.INTERESTS)


# Шаг 1 — интересы
@router.message(MainForm.INTERESTS)
async def process_interests(message: Message, state: FSMContext):
    await state.update_data(interests=message.text)
    await message.answer(
        f"Ваши интересы: {message.text}",
        reply_markup=ukb.interests_accept_keyboard()
    )


@router.callback_query(F.data == "accept_interests")
async def accept_interests(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(get_phrase("FORM", "TIME"))
    await state.set_state(MainForm.TIME)


@router.callback_query(F.data == "add_interests")
async def add_interests(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите ещё интересы:")
    await state.set_state(MainForm.ADD_INTERESTS)


@router.message(MainForm.ADD_INTERESTS)
async def process_add_interests(message: Message, state: FSMContext):
    data = await state.get_data()
    old_interests = data.get("interests", "")

    if old_interests:
        new_interests = f"{old_interests}, {message.text}"
    else:
        new_interests = message.text

    await state.update_data(interests=new_interests)
    await message.answer(
        f"Обновленные интересы: {new_interests}",
        reply_markup=ukb.interests_accept_keyboard()
    )


@router.callback_query(F.data == "delete_interests")
async def delete_interests(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите интересы заново:")
    await state.update_data(interests="")
    await state.set_state(MainForm.INTERESTS)


# Шаг 2 — время
@router.message(MainForm.TIME)
async def process_time(message: Message, state: FSMContext):
    if not is_valid_time(message.text):
        await message.answer("Некорректное время")
        return

    await state.update_data(time=message.text)

    await message.answer(
        f"Вы выбрали время: {message.text}\nТочно?",
        reply_markup=ukb.time_accept_keyboard()
    )


@router.callback_query(F.data == "accept_time")
async def accept_time(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer(
        get_phrase("FORM", "LOCATION"),
        reply_markup=ukb.location_keyboard
    )
    await state.set_state(MainForm.LOCATION)


@router.callback_query(F.data == "change_time")
async def change_time(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Введите время заново:")


# Шаг 3 — локация (обработка координат или текста)
@router.message(MainForm.LOCATION, F.location)
async def process_location_geo(message: Message, state: FSMContext):
    loc = message.location
    coords = f"{loc.latitude}, {loc.longitude}"
    await state.update_data(location=coords)

    await message.answer(
        f"Ваша локация: {coords}. Верно?",
        reply_markup=ukb.location_accept_keyboard()
    )


@router.message(MainForm.LOCATION)
async def process_location_text(message: Message, state: FSMContext):
    if not await is_valid_location(message.text):
        await message.answer("😕 Не удалось определить адрес. Попробуйте уточнить")
        return

    from src.yandex_api import get_coordinates, get_address
    coords = await get_coordinates(correction_location(message.text))
    address = await get_address(coords[0], coords[1])

    await state.update_data(location=f"{coords[0]}, {coords[1]}")

    await message.answer(
        f"Ваша локация: {address}. Верно?",
        reply_markup=ukb.location_accept_keyboard()
    )


@router.callback_query(F.data == "accept_location")
async def accept_location(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    data = await state.get_data()
    await send_summary(callback.message, data, state)


@router.callback_query(F.data == "change_location")
async def change_location(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await state.update_data(location="")
    await callback.message.answer("Введите локацию заново:")


# Итог - обновленная функция с маршрутом
async def send_summary(message: Message, data: dict, state: FSMContext):
    interests = data.get("interests")
    time = data.get("time")
    location = data.get("location")

    # Показываем что бот работает
    await message.answer("🔄 Создаю ваш персональный маршрут...")

    # Получаем маршрут от ИИ
    response = await request_to_llm(data)

    if not response["success"]:
        await message.answer(
            f"✅ Спасибо! Вот ваши данные:\n\n"
            f"✨ Интересы: {interests}\n"
            f"⏰ Время на прогулку: {time} часов\n"
            f"📍 Местоположение: {location}\n\n"
            f"❌ К сожалению, не удалось построить маршрут. Попробуйте позже.",
            reply_markup=ukb.main_keyboard
        )
        return

    # Формируем сообщение с таймлайном
    timeline_text = "🎯 Ваш персональный маршрут:\n\n"

    for item in response["timeline"]:
        timeline_text += f"⏰ {item['time']} - *{item['place']}*\n"
        timeline_text += f"   _{item['description']}_ ({item['duration']})\n\n"

    # Добавляем информацию о данных пользователя
    timeline_text += f"📋 Ваши данные:\n"
    timeline_text += f"✨ Интересы: {interests}\n"
    timeline_text += f"⏰ Время: {time} часов\n"
    timeline_text += f"📍 Локация: {location}\n\n"

    # Создаем кнопку для просмотра на карте
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗺️ Посмотреть маршрут на карте", url=response["map_url"])],
            [InlineKeyboardButton(text="🔄 Создать новый маршрут", callback_data="new_route")]
        ]
    )

    await message.answer(
        timeline_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# Обработка создания нового маршрута
@router.callback_query(F.data == "new_route")
async def new_route_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup()
    await callback.message.answer("Давайте создадим новый маршрут! Введите ваши интересы:")
    await state.set_state(MainForm.INTERESTS)