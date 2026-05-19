"""
Точка входа бота «Вопросы математики».

Telegram-бот для обучения математике с педагогической обратной связью.
"""

from __future__ import annotations

import logging
import sys

import telebot
from telebot.storage import StateMemoryStorage

import config
from database import Database
from handlers import register_handlers

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    setup_logging()

    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Создайте файл .env по образцу .env.example")
        sys.exit(1)

    from services.task_bank import ensure_task_files

    ensure_task_files()

    db = Database(config.DATABASE_PATH)
    db.init_schema()

    bot = telebot.TeleBot(config.BOT_TOKEN, state_storage=StateMemoryStorage())
    register_handlers(bot, db)

    logger.info("Бот «%s» запущен (модуль правил и шаблонов обратной связи)", config.BOT_NAME)
    bot.infinity_polling(timeout=60, long_polling_timeout=60)


if __name__ == "__main__":
    main()
