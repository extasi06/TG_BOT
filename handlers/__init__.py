"""Регистрация обработчиков Telegram."""

from __future__ import annotations

import telebot
from telebot import custom_filters

from database import Database
from handlers import feedback, profile, start, statistics, tasks
from services.feedback_engine import FeedbackEngine
from services.practice_tracker import PracticeTracker
from services.statistics_service import StatisticsService
from services.task_service import TaskService


def register_handlers(bot: telebot.TeleBot, db: Database) -> None:
    task_service = TaskService()
    feedback_engine = FeedbackEngine(task_service)
    practice_tracker = PracticeTracker(db)
    stats_service = StatisticsService(db, task_service, practice_tracker)

    ctx = {
        "db": db,
        "task_service": task_service,
        "feedback_engine": feedback_engine,
        "practice_tracker": practice_tracker,
        "stats_service": stats_service,
    }

    start.register(bot, ctx)
    profile.register(bot, ctx)
    statistics.register(bot, ctx)
    feedback.register(bot, ctx)
    tasks.register(bot, ctx)

    bot.add_custom_filter(custom_filters.StateFilter(bot))
