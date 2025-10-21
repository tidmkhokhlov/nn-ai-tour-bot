from aiogram import Router

def get_handlers_router() -> Router:
    from src.bot.handlers import (main_handlers)

    router = Router()
    router.include_router(main_handlers.router)

    return router