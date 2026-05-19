"""Общие функции для обработчиков."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import config
from handlers.states import UserState
from keyboards.menu import main_menu_kb
from services.task_service import TaskService
from utils.difficulty import difficulty_label, level_from_xp
from utils.markdown import escape_markdown


def welcome_text(first_name: str | None) -> str:
    name = first_name or "ученик"
    return (
        f"📐 *{config.BOT_NAME}*\n\n"
        f"Привет, *{name}*! 👋\n\n"
        "Я помогу тебе учиться математике через "
        "*педагогическую обратную связь*: задачи, подсказки "
        "и разбор ошибок без готового решения.\n\n"
        "Выбери действие в меню ниже 👇"
    )


def format_task_message(user: dict[str, Any], task: dict[str, Any], topic: str, ts: TaskService) -> str:
    emoji = ts.topic_emoji(topic)
    title = ts.topic_title(topic)
    diff = task["difficulty"]
    level = level_from_xp(user.get("xp", 0))
    idx = user.get("task_index", 0) + 1
    total = ts.count_tasks(topic)

    return (
        f"📐 *{config.BOT_NAME}*\n\n"
        f"{emoji} *Тема:* {title}\n"
        f"⭐ *Сложность:* {diff}/5 ({difficulty_label(diff)})\n"
        f"📈 *Уровень:* {level} | XP: {user.get('xp', 0)}\n"
        f"📋 *Задача {idx}/{total}*\n\n"
        f"*Условие:*\n{escape_markdown(task['question'])}\n\n"
        "_Введи ответ текстом (например: `3/4` или `42`)._"
    )


def set_state(bot: Any, chat_id: int, user_id: int, state: Any) -> None:
    bot.set_state(user_id, state, chat_id)


def clear_session_task(db: Any, user_id: int) -> None:
    db.update_user(
        user_id,
        current_task_id=None,
        hints_used_session=0,
        task_started_at=None,
    )


def show_main_menu(bot: Any, chat_id: int, user_id: int, text: str | None = None) -> None:
    set_state(bot, chat_id, user_id, UserState.main_menu)
    bot.send_message(
        chat_id,
        text or welcome_text(None),
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )


def parse_started_at(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        started = datetime.fromisoformat(value)
        return max(0.0, (datetime.utcnow() - started).total_seconds())
    except ValueError:
        return 0.0
