"""Геймификация, достижения и отчёты."""

from __future__ import annotations

import json
from typing import Any, Optional

import config
from database import Database
from services.task_service import TaskService
from utils.difficulty import level_from_xp, xp_to_next_level


class StatisticsService:
    """Агрегация статистики и проверка достижений."""

    def __init__(
        self,
        db: Database,
        task_service: TaskService,
        practice_tracker: Any = None,
    ) -> None:
        self.db = db
        self.task_service = task_service
        self.practice_tracker = practice_tracker

    def accuracy_percent(self, user_id: int) -> float:
        stats = self.db.get_statistics(user_id)
        total = stats["total_attempts"]
        if total == 0:
            return 0.0
        return round(100.0 * stats["correct_count"] / total, 1)

    def format_profile(self, user: dict[str, Any]) -> str:
        stats = self.db.get_statistics(user["user_id"])
        topic_name = "не выбрана"
        if user.get("current_topic"):
            topic_name = self.task_service.topic_title(user["current_topic"])

        accuracy = self.accuracy_percent(user["user_id"])
        achievements = self.db.get_achievements(user["user_id"])
        ach_lines = "\n".join(
            f"  • {config.ACHIEVEMENTS.get(c, c)}"
            for c in achievements
        ) or "  _Пока нет — решай задачи!_"

        xp = user.get("xp", 0)
        level = level_from_xp(xp)
        to_next = xp_to_next_level(xp)

        return (
            f"👤 *Профиль*\n\n"
            f"Имя: *{user.get('first_name') or 'Ученик'}*\n"
            f"Тема: {topic_name}\n"
            f"Уровень: *{level}* (XP: {xp}, до след.: {to_next})\n\n"
            f"✅ Решено верно: {stats['correct_count']}\n"
            f"❌ Ошибок: {stats['wrong_count']}\n"
            f"📊 Точность: {accuracy}%\n"
            f"🔥 Текущая серия: {user.get('streak', 0)}\n"
            f"🏆 Лучшая серия: {user.get('max_streak', 0)}\n\n"
            f"*Достижения:*\n{ach_lines}"
        )

    def format_statistics(self, user_id: int) -> str:
        stats = self.db.get_statistics(user_id)
        summary = self.db.get_global_stats_summary(user_id)
        popular: dict[str, int] = json.loads(stats.get("popular_errors") or "{}")
        popular_lines = "\n".join(
            f"  • {config.ERROR_LABELS.get(k, k)}: {v}"
            for k, v in sorted(popular.items(), key=lambda x: -x[1])[:5]
        ) or "  _Пока нет данных_"

        avg_time = 0.0
        if stats["total_attempts"] > 0:
            avg_time = round(stats["total_time_sec"] / stats["total_attempts"], 1)

        diff_lines = []
        for row in summary.get("by_difficulty", []):
            d = row["difficulty"]
            total = row["total"]
            correct = row["correct"] or 0
            pct = round(100 * correct / total, 1) if total else 0
            diff_lines.append(f"  • Сложность {d}: {correct}/{total} ({pct}%)")
        diff_block = "\n".join(diff_lines) or "  _Нет попыток_"

        learning_block = ""
        if self.practice_tracker:
            report_lines = []
            for r in self.db.get_all_error_learning(user_id):
                err = r["error_type"]
                label = config.ERROR_LABELS.get(err, err)
                seen = r["times_seen"]
                after = r.get("attempts_after_feedback", 0)
                ok = r.get("correct_after_feedback", 0)
                sim_a = r.get("similar_attempts", 0)
                sim_ok = r.get("similar_correct", 0)
                after_pct = round(100 * ok / after, 1) if after else "—"
                sim_pct = round(100 * sim_ok / sim_a, 1) if sim_a else "—"
                report_lines.append(
                    f"  • {label}: {seen} ош., после ОС {after_pct}%, аналог. {sim_pct}%"
                )
            learning_block = (
                "\n\n*Эффект обратной связи:*\n"
                + ("\n".join(report_lines) if report_lines else "  _Нет данных_")
            )
            apr = self.db.get_aprobation_summary(user_id)
            if apr.get("after_fb"):
                learning_block += (
                    f"\n\n📈 *Итого после подсказок:* "
                    f"{apr.get('after_feedback_success_pct', 0)}% верных"
                )

        return (
            f"📊 *Статистика*\n\n"
            f"Всего ответов: {stats['total_attempts']}\n"
            f"Верных: {stats['correct_count']}\n"
            f"Неверных: {stats['wrong_count']}\n"
            f"Подсказок использовано: {stats['hints_count']}\n"
            f"⏱ Среднее время: {avg_time} сек\n\n"
            f"*По сложности:*\n{diff_block}\n\n"
            f"*Частые ошибки:*\n{popular_lines}"
            f"{learning_block}"
        )

    def check_achievements(
        self,
        user: dict[str, Any],
        *,
        is_correct: bool,
        used_hint: bool,
        stats: dict[str, Any],
    ) -> list[str]:
        """Проверяет и выдаёт новые достижения. Возвращает список кодов."""
        new: list[str] = []
        uid = user["user_id"]

        if is_correct and self.db.add_achievement(uid, "first_correct"):
            new.append("first_correct")

        streak = user.get("streak", 0)
        if streak >= 5 and self.db.add_achievement(uid, "streak_5"):
            new.append("streak_5")
        if streak >= 10 and self.db.add_achievement(uid, "streak_10"):
            new.append("streak_10")

        level = level_from_xp(user.get("xp", 0))
        if level >= 5 and self.db.add_achievement(uid, "level_5"):
            new.append("level_5")

        if stats.get("no_hint_streak", 0) >= 10:
            if self.db.add_achievement(uid, "no_hints_10"):
                new.append("no_hints_10")

        topic = user.get("current_topic")
        if topic and is_correct:
            idx = user.get("task_index", 0)
            total = self.task_service.count_tasks(topic)
            if idx >= total:
                code = {
                    "fractions": "topic_fractions",
                    "arithmetic": "topic_arithmetic",
                    "word_problems": "topic_word",
                }.get(topic)
                if code and self.db.add_achievement(uid, code):
                    new.append(code)

        return new

    def format_achievement_notice(self, codes: list[str]) -> Optional[str]:
        if not codes:
            return None
        lines = [config.ACHIEVEMENTS.get(c, c) for c in codes]
        return "🎉 *Новое достижение!*\n" + "\n".join(f"• {line}" for line in lines)
