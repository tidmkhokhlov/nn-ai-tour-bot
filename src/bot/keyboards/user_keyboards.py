from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.utils.json_loader import get_button_text

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=get_button_text("BUTTONS", "MAKE_PLAN"))]
    ],
    resize_keyboard=True
)

location_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📍 Отправить геопозицию", request_location=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

def interests_accept_keyboard():
    keyboard = InlineKeyboardBuilder()
    choice_list = [
        (get_button_text("BUTTONS", "EVERYTHING_CORRECT"), "accept_interests"),
        (get_button_text("BUTTONS", "ADD_INTERESTS"), "add_interests"),
        (get_button_text("BUTTONS", "RESET_INTERESTS"), "delete_interests")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()

def time_accept_keyboard():
    keyboard = InlineKeyboardBuilder()
    choice_list = [
        (get_button_text("BUTTONS", "EVERYTHING_CORRECT"), "accept_time"),
        (get_button_text("BUTTONS", "CHANGE_TIME"), "change_time")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()

def location_accept_keyboard():
    keyboard = InlineKeyboardBuilder()
    choice_list = [
        (get_button_text("BUTTONS", "EVERYTHING_CORRECT"), "accept_location"),
        (get_button_text("BUTTONS", "CHANGE_LOCATION"), "change_location")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()