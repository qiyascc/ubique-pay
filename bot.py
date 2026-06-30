#!/usr/bin/env python3
"""Ubique Pay — Telegram bot.

On /start it opens the Mini App (a Telegram Web App button). The Mini App
authenticates the user against the backend with signed initData.

    TELEGRAM_BOT_TOKEN=... PUBLIC_BASE_URL=https://pay.example.com python bot.py

Requires: pip install aiogram  (and an https PUBLIC_BASE_URL — Telegram only
opens Web Apps served over https).
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
APP_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/") + "/app/"


async def main():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (and PUBLIC_BASE_URL).")

    from aiogram import Bot, Dispatcher
    from aiogram.filters import CommandStart
    from aiogram.types import (
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        Message,
        WebAppInfo,
    )

    dp = Dispatcher()

    @dp.message(CommandStart())
    async def start(message: Message):
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💸 Open Ubique Pay", web_app=WebAppInfo(url=APP_URL))
        ]])
        await message.answer(
            "Send money to anyone, anywhere — card in, card out, settled as USDT.",
            reply_markup=kb,
        )

    bot = Bot(TOKEN)
    print(f"Bot polling. Mini App: {APP_URL}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
