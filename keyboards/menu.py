"""Главное меню и навигация."""

from __future__ import annotations

from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

import config


def main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📚 Выбрать тему", callback_data="menu:topics"),
        InlineKeyboardButton("👤 Профиль", callback_data="menu:profile"),
    )
    kb.add(
        InlineKeyboardButton("📊 Статистика", callback_data="menu:stats"),
        InlineKeyboardButton("📩 Feedback", callback_data="menu:feedback"),
    )
    kb.add(
        InlineKeyboardButton("🔄 Перезапуск", callback_data="menu:restart"),
    )

    return kb


def topics_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for key, meta in config.TOPICS.items():
        kb.add(
            InlineKeyboardButton(
                f"{meta['emoji']} {meta['title']}",
                callback_data=f"topic:{key}",
            )
        )
    kb.add(InlineKeyboardButton("◀️ В меню", callback_data="menu:main"))
    return kb


def back_to_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Главное меню", callback_data="menu:main"))
    return kb
