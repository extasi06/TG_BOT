"""Клавиатуры во время решения задач."""

from __future__ import annotations

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup


def solving_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💡 Подсказка", callback_data="task:hint"),
        InlineKeyboardButton("🔄 В меню", callback_data="menu:restart"),
    )
    return kb


def retry_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔁 Попробовать снова", callback_data="task:retry"),
        InlineKeyboardButton("📚 Аналогичная задача", callback_data="task:similar"),
        InlineKeyboardButton("◀️ Главное меню", callback_data="menu:main"),
    )
    return kb


def correct_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➡️ Следующая задача", callback_data="task:next"))
    return kb
