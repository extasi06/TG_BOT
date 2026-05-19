"""Учёт повторяемости ошибок и эффекта обратной связи (до/после)."""

from __future__ import annotations

from typing import Any, Optional

from database import Database


class PracticeTracker:
    """Метрики для апробации: снижение повторов, рост успеха на аналогичных задачах."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def on_error(
        self,
        user_id: int,
        task_id: str,
        error_type: str,
        user_answer: str,
    ) -> dict[str, Any]:
        """Фиксирует ошибку; возвращает счётчики для обратной связи."""
        learning = self.db.record_error_learning(user_id, error_type)
        repeat_count = learning["times_seen"]
        is_repeat = repeat_count > 1
        self.db.log_feedback(user_id, task_id, error_type, user_answer, int(is_repeat))
        self.db.update_user(
            user_id,
            last_error_type=error_type,
            active_feedback_error=error_type,
            similar_practice_mode=0,
        )
        return {
            "repeat_count": repeat_count,
            "is_repeat": is_repeat,
            "times_repeated": learning.get("times_repeated", 0),
        }

    def on_feedback_delivered(self, user_id: int, error_type: str) -> None:
        self.db.mark_feedback_shown(user_id, error_type)

    def start_similar_practice(self, user_id: int, error_type: str) -> None:
        self.db.update_user(
            user_id,
            similar_practice_mode=1,
            active_feedback_error=error_type,
        )
        self.db.increment_similar_attempts(user_id, error_type)

    def on_attempt_after_feedback(
        self,
        user_id: int,
        *,
        is_correct: bool,
        is_similar: bool,
        error_type: Optional[str],
    ) -> Optional[str]:
        """Обновляет метрики «после обратной связи»; возвращает текст прогресса."""
        user = self.db.get_user(user_id)
        if not user:
            return None
        err = error_type or user.get("active_feedback_error")
        if not err:
            return None

        if is_similar or user.get("similar_practice_mode"):
            if is_correct:
                self.db.record_similar_success(user_id, err)
                self.db.update_user(user_id, similar_practice_mode=0, active_feedback_error=None)
                stats = self.db.get_error_learning(user_id, err)
                rate = self._similar_success_rate(stats)
                return (
                    f"Верно на аналогичной задаче! "
                    f"Успех после подсказок по этому типу: {rate}%."
                )
            return "Пока неверно — перечитай правило в прошлом сообщении."

        if is_correct:
            self.db.record_correct_after_feedback(user_id, err)
            self.db.update_user(user_id, active_feedback_error=None)
            stats = self.db.get_error_learning(user_id, err)
            rate = self._after_feedback_rate(stats)
            return f"Отлично! Доля верных после обратной связи по типу «{err}»: {rate}%."

        if err:
            self.db.record_error_repeat(user_id, err)
        return None

    def get_learning_report(self, user_id: int) -> str:
        rows = self.db.get_all_error_learning(user_id)
        if not rows:
            return "  _Нет данных по типам ошибок_"
        lines = []
        for r in rows:
            err = r["error_type"]
            label = err  # caller may wrap with config.ERROR_LABELS
            seen = r["times_seen"]
            repeated = r.get("times_repeated", 0)
            after = r.get("attempts_after_feedback", 0)
            correct_after = r.get("correct_after_feedback", 0)
            sim_att = r.get("similar_attempts", 0)
            sim_ok = r.get("similar_correct", 0)
            after_pct = round(100 * correct_after / after, 1) if after else 0
            sim_pct = round(100 * sim_ok / sim_att, 1) if sim_att else 0
            repeat_pct = round(100 * repeated / seen, 1) if seen else 0
            lines.append(
                f"  • {label}: ошибок {seen}, повторов {repeat_pct}%, "
                f"после ОС {after_pct}%, аналогичные {sim_pct}%"
            )
        return "\n".join(lines)

    @staticmethod
    def _after_feedback_rate(stats: dict) -> float:
        a = stats.get("attempts_after_feedback", 0)
        c = stats.get("correct_after_feedback", 0)
        return round(100 * c / a, 1) if a else 0.0

    @staticmethod
    def _similar_success_rate(stats: dict) -> float:
        a = stats.get("similar_attempts", 0)
        c = stats.get("similar_correct", 0)
        return round(100 * c / a, 1) if a else 0.0
