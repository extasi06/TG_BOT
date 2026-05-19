"""Обратная связь от пользователя."""

from __future__ import annotations

from typing import Any

import telebot

from handlers.common import set_state
from handlers.states import UserState
from keyboards.menu import back_to_menu_kb


def register(bot: telebot.TeleBot, ctx: dict[str, Any]) -> None:
    db = ctx["db"]

    @bot.callback_query_handler(func=lambda c: c.data == "menu:feedback")
    def cb_feedback_start(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        set_state(bot, call.message.chat.id, call.from_user.id, UserState.waiting_feedback)
        bot.edit_message_text(
            "📩 *Обратная связь*\n\n"
            "Напиши сообщение: пожелания, замечания или идеи для улучшения бота.\n"
            "Отправь одним сообщением.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )

    @bot.message_handler(state=UserState.waiting_feedback, content_types=["text"])
    def on_feedback(message: telebot.types.Message) -> None:
        text = (message.text or "").strip()
        if len(text) < 3:
            bot.send_message(
                message.chat.id,
                "Сообщение слишком короткое. Напиши хотя бы 3 символа.",
            )
            return
        db.save_feedback(message.from_user.id, text)
        set_state(bot, message.chat.id, message.from_user.id, UserState.main_menu)
        bot.send_message(
            message.chat.id,
            "✅ Спасибо! Твоё сообщение сохранено.\n\n"
            "Мы учтём его при развитии бота.",
            parse_mode="Markdown",
            reply_markup=back_to_menu_kb(),
        )
