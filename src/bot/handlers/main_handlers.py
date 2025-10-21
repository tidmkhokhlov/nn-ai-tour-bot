import re

from aiogram import F
from aiogram.fsm.context import FSMContext

from src.bot.states.main_states import MainForm
from src.llm import request