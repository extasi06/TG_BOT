"""Конфигурация бота «Вопросы математики»."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(DATA_DIR / "bot.db"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

BOT_NAME = "Вопросы математики"

TOPICS: dict[str, dict[str, str]] = {
    "fractions": {
        "title": "Дроби",
        "file": "fractions.json",
        "emoji": "🔢",
    },
    "arithmetic": {
        "title": "Арифметика",
        "file": "arithmetic.json",
        "emoji": "➕",
    },
    "word_problems": {
        "title": "Текстовые задачи",
        "file": "word_problems.json",
        "emoji": "📝",
    },
    "percentages": {
        "title": "Проценты",
        "file": "percentages.json",
        "emoji": "📊",
    },
}

# Опыт за сложность (1–5)
XP_PER_DIFFICULTY: dict[int, int] = {1: 10, 2: 15, 3: 20, 4: 30, 5: 40}
XP_HINT_MULTIPLIER: float = 0.5
LEVEL_XP_STEP: int = 100

# Коды достижений
ACHIEVEMENTS: dict[str, str] = {
    "first_correct": "🎯 Первый верный ответ",
    "streak_5": "🔥 Серия из 5 правильных",
    "streak_10": "⚡ Серия из 10 правильных",
    "level_5": "⭐ Достигнут 5 уровень",
    "no_hints_10": "🧠 10 задач без подсказок",
    "topic_fractions": "🔢 Мастер дробей",
    "topic_arithmetic": "➕ Мастер арифметики",
    "topic_word": "📝 Мастер текстовых задач",
}

# Локализованные названия типовых ошибок
ERROR_LABELS: dict[str, str] = {
    "wrong_common_denominator": "ошибка приведения к общему знаменателю",
    "added_numerators_only": "сложили только числители",
    "sign_error": "ошибка со знаком",
    "order_of_operations": "нарушен порядок действий",
    "fraction_addition": "неправильное сложение дробей",
    "fraction_multiplication": "ошибка умножения дробей",
    "division_error": "ошибка деления",
    "decimal_place": "ошибка в разрядах",
    "unit_conversion": "ошибка перевода единиц",
    "misread_condition": "неверно прочитано условие",
    "calculation_error": "арифметическая ошибка",
    "percent_error": "ошибка в процентах",
}
