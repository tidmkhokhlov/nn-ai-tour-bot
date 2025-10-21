from aiogram.fsm.state import StatesGroup, State

class MainForm(StatesGroup):
    INTERESTS = State()
    TIME = State()
    LOCATION = State()