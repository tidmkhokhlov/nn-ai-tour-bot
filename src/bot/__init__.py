from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from src.bot.handlers import get_handlers_router

load_dotenv()
BOT_TOKEN = getenv("BOT_TOKEN")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2)
)
dp = Dispatcher()
dp.include_router(get_handlers_router())