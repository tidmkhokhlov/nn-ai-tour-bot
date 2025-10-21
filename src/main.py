import asyncio
import logging
import sys

from src.bot import bot, dp

async def main():
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print(e)


if __name__ == "__main__":
    try:
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
        asyncio.run(main())
    except KeyboardInterrupt:
        print('FINISHED')
