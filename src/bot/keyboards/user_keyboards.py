from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Составить план прогулки")]
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
        ("Все верно", "accept_interests"),
        ("Добавить ещё интересов", "add_interests"),
        ("Сбросить интересы", "delete_interests")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()

def time_accept_keyboard():
    keyboard = InlineKeyboardBuilder()
    choice_list = [
        ("Далее", "accept_time"),
        ("Изменить время", "change_time")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()

def location_accept_keyboard():
    keyboard = InlineKeyboardBuilder()
    choice_list = [
        ("Да", "accept_location"),
        ("Изменить место", "change_location")
    ]
    for text, callback_data in choice_list:
        keyboard.add(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard.adjust(1)
    return keyboard.as_markup()