"""Решение задач, модуль обратной связи и закрепление."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import telebot

import config
from handlers.common import format_task_message, parse_started_at, set_state
from handlers.states import UserState
from keyboards.menu import main_menu_kb
from keyboards.tasks import correct_kb, retry_kb, solving_kb
from utils.difficulty import adapt_difficulty, calculate_xp, level_from_xp, pick_task_index_for_difficulty
from utils.markdown import escape_markdown
from utils.validators import is_plausible_answer

logger = logging.getLogger(__name__)

_recent_wrong: dict[int, int] = {}


def register(bot: telebot.TeleBot, ctx: dict[str, Any]) -> None:
    db = ctx["db"]
    ts = ctx["task_service"]
    fb = ctx["feedback_engine"]
    tracker = ctx["practice_tracker"]
    stats_service = ctx["stats_service"]

    def _get_user(user_id: int, username: str | None, first_name: str | None) -> dict:
        return db.get_or_create_user(user_id, username, first_name)

    def send_task(chat_id: int, user_id: int, edit_message_id: int | None = None) -> None:
        user = db.get_user(user_id)
        if not user or not user.get("current_topic"):
            bot.send_message(chat_id, "Сначала выбери тему в меню 📚")
            return

        topic = user["current_topic"]
        idx = user.get("task_index", 0)
        difficulty = user.get("current_difficulty", 1)
        tasks = ts.load_topic(topic)
        if not tasks:
            bot.send_message(chat_id, "⚠️ Задачи для темы не найдены.")
            return

        idx = pick_task_index_for_difficulty(tasks, difficulty, idx)

        solved_ids = set(db.get_solved_task_ids(user_id, topic))
        available = [i for i, t in enumerate(tasks) if t["id"] not in solved_ids]

        if available:
            # Выбираем доступную задачу, минимизируя сначала разницу в сложности,
            # затем расстояние по индексу от текущего `idx` — это сглаживает резкие
            # перескакивания между уровнями сложности.
            def score(i: int) -> tuple[int, int]:
                return (abs(tasks[i]["difficulty"] - difficulty), abs(i - idx))

            available.sort(key=score)
            idx = available[0]

        if idx >= len(tasks):
            bot.send_message(
                chat_id,
                f"🎉 Ты прошёл все задачи по теме «{ts.topic_title(topic)}»!",
                reply_markup=main_menu_kb(),
            )
            set_state(bot, chat_id, user_id, UserState.main_menu)
            return

        task = tasks[idx]
        ts.sync_tasks_to_db(db, topic)
        db.update_user(
            user_id,
            task_index=idx,
            current_task_id=task["id"],
            hints_used_session=0,
            task_started_at=datetime.utcnow().isoformat(),
        )
        user = db.get_user(user_id) or user
        text = format_task_message(user, task, topic, ts)
        set_state(bot, chat_id, user_id, UserState.solving)

        if edit_message_id:
            bot.edit_message_text(
                text, chat_id, edit_message_id,
                parse_mode="Markdown", reply_markup=solving_kb(),
            )
        else:
            bot.send_message(
                chat_id, text, parse_mode="Markdown", reply_markup=solving_kb(),
            )

    def start_topic(chat_id: int, user_id: int, topic: str, message_id: int) -> None:
        ts.sync_tasks_to_db(db, topic)
        db.update_user(
            user_id,
            current_topic=topic,
            task_index=0,
            current_difficulty=1,
            current_task_id=None,
            hints_used_session=0,
            active_feedback_error=None,
            similar_practice_mode=0,
        )
        _recent_wrong[user_id] = 0
        bot.edit_message_text(
            f"✅ Тема: *{ts.topic_title(topic)}*\n\nНачинаем с простых задач!",
            chat_id, message_id, parse_mode="Markdown",
        )
        send_task(chat_id, user_id)

    @bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("topic:"))
    def cb_select_topic(call: telebot.types.CallbackQuery) -> None:
        topic = call.data.split(":", 1)[1]
        bot.answer_callback_query(call.id)
        _get_user(call.from_user.id, call.from_user.username, call.from_user.first_name)
        if topic not in config.TOPICS:
            bot.answer_callback_query(call.id, "Неизвестная тема", show_alert=True)
            return
        start_topic(call.message.chat.id, call.from_user.id, topic, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data in ("menu:hint", "task:hint"))
    def cb_hint(call: telebot.types.CallbackQuery) -> None:
        user = db.get_user(call.from_user.id)
        if not user or not user.get("current_task_id"):
            bot.answer_callback_query(call.id, "Сначала начни решать задачу", show_alert=True)
            return
        task = ts.get_task(user["current_topic"], user.get("task_index", 0))
        if not task:
            return
        db.update_user(call.from_user.id, hints_used_session=user.get("hints_used_session", 0) + 1)
        bot.answer_callback_query(call.id, "Подсказка")
        bot.send_message(
            call.message.chat.id,
            f"💡 *Подсказка* (награда уменьшена):\n\n{escape_markdown(task['hint'])}",
            parse_mode="Markdown",
        )

    @bot.callback_query_handler(func=lambda c: c.data == "task:retry")
    def cb_retry(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        send_task(call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "task:next")
    def cb_next(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        user = db.get_user(call.from_user.id)
        if user:
            db.update_user(call.from_user.id, task_index=user.get("task_index", 0) + 1)
        send_task(call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data == "task:skip")
    def cb_skip(call: telebot.types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id, "Пропущено")
        user = db.get_user(call.from_user.id)
        if user:
            db.update_user(call.from_user.id, task_index=user.get("task_index", 0) + 1, streak=0)
        send_task(call.message.chat.id, call.from_user.id)

    @bot.callback_query_handler(func=lambda c: c.data == "task:similar")
    def cb_similar(call: telebot.types.CallbackQuery) -> None:
        user = db.get_user(call.from_user.id)
        if not user or not user.get("current_topic"):
            return
        topic = user["current_topic"]
        idx = user.get("task_index", 0)
        task = ts.get_task(topic, idx)
        if not task:
            return
        err = user.get("active_feedback_error") or user.get("last_error_type") or "calculation_error"
        tracker.start_similar_practice(call.from_user.id, err)
        similar_idx = fb.find_similar_task_index(topic, idx, task, err)
        if similar_idx is not None:
            db.update_user(call.from_user.id, task_index=similar_idx)
        bot.answer_callback_query(call.id, "Аналогичная задача для закрепления")
        send_task(call.message.chat.id, call.from_user.id, call.message.message_id)

    @bot.message_handler(state=UserState.solving, content_types=["text"])
    def on_answer(message: telebot.types.Message) -> None:
        user = _get_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        answer = (message.text or "").strip()
        if not is_plausible_answer(answer):
            bot.send_message(
                message.chat.id,
                "⚠️ Ответ должен быть числом или дробью. Напиши ответ правильно, например: `7`, `3/4`.",
                parse_mode="Markdown",
            )
            return

        topic = user.get("current_topic")
        if not topic:
            bot.send_message(message.chat.id, "Выбери тему в меню 📚")
            return

        idx = user.get("task_index", 0)
        task = ts.get_task(topic, idx)
        if not task:
            bot.send_message(message.chat.id, "Задача не найдена.")
            return

        time_spent = parse_started_at(user.get("task_started_at"))
        used_hint = user.get("hints_used_session", 0) > 0
        is_similar = bool(user.get("similar_practice_mode"))
        after_fb = bool(user.get("active_feedback_error"))
        fb_err = user.get("active_feedback_error")
        is_correct = ts.check_answer(answer, task["answer"])

        if is_correct:
            _handle_correct(
                message, user, task, topic, answer, time_spent, used_hint,
                is_similar, after_fb, fb_err,
            )
        else:
            _handle_wrong(message, user, task, topic, answer, time_spent, used_hint, idx)

    def _handle_correct(
        message: telebot.types.Message,
        user: dict,
        task: dict,
        topic: str,
        answer: str,
        time_spent: float,
        used_hint: bool,
        is_similar: bool,
        after_fb: bool,
        fb_err: str | None,
    ) -> None:
        uid = user["user_id"]
        diff = task["difficulty"]
        xp = calculate_xp(diff, used_hint)
        new_xp = user.get("xp", 0) + xp
        streak = user.get("streak", 0) + 1
        max_streak = max(user.get("max_streak", 0), streak)
        new_level = level_from_xp(new_xp)
        _recent_wrong[uid] = 0

        progress_msg = tracker.on_attempt_after_feedback(
            uid,
            is_correct=True,
            is_similar=is_similar,
            error_type=fb_err,
        )

        db.record_attempt(
            uid, task["id"], answer, True, diff, time_spent, None, used_hint, xp,
            is_similar_practice=is_similar,
            after_feedback=after_fb,
            feedback_error_type=fb_err,
        )
        stats = db.update_statistics(
            uid, is_correct=True, time_spent_sec=time_spent, error_type=None, used_hint=used_hint,
        )
        db.update_user(
            uid,
            xp=new_xp,
            streak=streak,
            max_streak=max_streak,
            level=new_level,
            current_difficulty=adapt_difficulty(user.get("current_difficulty", 1), streak, 0),
            task_index=user.get("task_index", 0) + 1,
        )
        user = db.get_user(uid) or user
        new_ach = stats_service.check_achievements(
            user, is_correct=True, used_hint=used_hint, stats=stats,
        )
        ach_text = stats_service.format_achievement_notice(new_ach)

        extra = f"\n\n{escape_markdown(progress_msg)}" if progress_msg else ""
        hint_note = "\n💡 _Награда уменьшена из‑за подсказки._" if used_hint else ""
        text = (
            f"✅ *Верно!* +{xp} XP\n🔥 Серия: {streak}\n📈 Уровень: {new_level}"
            f"{hint_note}{extra}\n\n"
            f"📖 *Объяснение:*\n{escape_markdown(task.get('explanation', ''))}"
        )
        set_state(bot, message.chat.id, uid, UserState.waiting_next_task)
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=correct_kb())
        if ach_text:
            bot.send_message(message.chat.id, ach_text, parse_mode="Markdown")

    @bot.message_handler(state=UserState.waiting_next_task, content_types=["text"])
    def on_waiting_next(message: telebot.types.Message) -> None:
        bot.send_message(
            message.chat.id,
            "Сначала нажми кнопку «➡️ Следующая задача», и только потом отправляй новый ответ.",
            parse_mode="Markdown",
        )

    def _handle_wrong(
        message: telebot.types.Message,
        user: dict,
        task: dict,
        topic: str,
        answer: str,
        time_spent: float,
        used_hint: bool,
        idx: int,
    ) -> None:
        uid = user["user_id"]
        diff = task["difficulty"]
        _recent_wrong[uid] = _recent_wrong.get(uid, 0) + 1

        classification = fb.classify(task, answer, topic)
        error_type = classification.error_type
        err_info = tracker.on_error(uid, task["id"], error_type, answer)

        package = fb.build_feedback(
            task=task,
            user_answer=answer,
            topic=topic,
            current_index=idx,
            repeat_count=err_info["repeat_count"],
        )
        tracker.on_feedback_delivered(uid, error_type)

        if user.get("similar_practice_mode") or user.get("active_feedback_error"):
            tracker.on_attempt_after_feedback(
                uid, is_correct=False, is_similar=bool(user.get("similar_practice_mode")), error_type=error_type,
            )

        db.record_attempt(
            uid, task["id"], answer, False, diff, time_spent, error_type, used_hint, 0,
            is_similar_practice=bool(user.get("similar_practice_mode")),
            after_feedback=bool(user.get("active_feedback_error")),
            feedback_error_type=error_type,
        )
        stats = db.update_statistics(
            uid, is_correct=False, time_spent_sec=time_spent, error_type=error_type, used_hint=used_hint,
        )
        db.update_user(
            uid,
            streak=0,
            current_difficulty=adapt_difficulty(
                user.get("current_difficulty", 1), user.get("streak", 0), _recent_wrong[uid],
            ),
            last_error_type=error_type,
        )
        stats_service.check_achievements(
            user, is_correct=False, used_hint=used_hint, stats=stats,
        )

        bot.send_message(
            message.chat.id,
            package.message,
            parse_mode="Markdown",
            reply_markup=retry_kb(),
        )
