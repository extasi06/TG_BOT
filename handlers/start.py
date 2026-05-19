"""Команда /start и главное меню."""

from __future__ import annotations

from typing import Any

import telebot

import config
from handlers.common import clear_session_task, set_state, show_main_menu, welcome_text
from handlers.states import UserState
from keyboards.menu import main_menu_kb, topics_kb


def register(bot: telebot.TeleBot, ctx: dict[str, Any]) -> None:
    db = ctx["db"]

    @bot.message_handler(commands=["start"])
    def cmd_start(message: telebot.types.Message) -> None:
        user = db.get_or_create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        set_state(bot, message.chat.id, message.from_user.id, UserState.main_menu)
        bot.send_message(
            message.chat.id,
            welcome_text(user.get("first_name")),
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

    @bot.message_handler(commands=["menu"])
    def cmd_menu(message: telebot.types.Message) -> None:
        db.get_or_create_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        set_state(bot, message.chat.id, message.from_user.id, UserState.main_menu)
        bot.send_message(
            message.chat.id,
            f"📐 *{config.BOT_NAME}* — главное меню",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu:main")
    def cb_main_menu(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        clear_session_task(db, call.from_user.id)
        set_state(bot, call.message.chat.id, call.from_user.id, UserState.main_menu)
        bot.edit_message_text(
            f"📐 *{config.BOT_NAME}* — главное меню",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu:topics")
    def cb_topics(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        set_state(bot, call.message.chat.id, call.from_user.id, UserState.choosing_topic)
        bot.edit_message_text(
            "📚 *Выбери тему:*\n\nЗадачи идут от простых к сложным.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=topics_kb(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "menu:restart")
    def cb_restart(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id, "Сессия сброшена. Статистика сохранена.")
        clear_session_task(db, call.from_user.id)
        set_state(bot, call.message.chat.id, call.from_user.id, UserState.main_menu)
        bot.edit_message_text(
            "🔄 *Перезапуск*\n\nТекущая задача сброшена. Статистика сохранена.\n\n"
            f"📐 *{config.BOT_NAME}* — главное меню",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=main_menu_kb(),
        )
