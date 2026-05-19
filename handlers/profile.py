"""Профиль пользователя."""

from __future__ import annotations

from typing import Any

import telebot

from handlers.states import UserState
from keyboards.menu import back_to_menu_kb


def register(bot: telebot.TeleBot, ctx: dict[str, Any]) -> None:
    db = ctx["db"]
    stats_service = ctx["stats_service"]

    @bot.callback_query_handler(func=lambda c: c.data == "menu:profile")
    def cb_profile(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        user = db.get_or_create_user(
            call.from_user.id,
            call.from_user.username,
            call.from_user.first_name,
        )
        text = stats_service.format_profile(user)
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
