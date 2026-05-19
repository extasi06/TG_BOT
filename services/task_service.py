"""Загрузка задач и анализ типовых ошибок."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import config
from utils.validators import answers_equal

logger = logging.getLogger(__name__)


class TaskService:
    """Работа с банком задач из JSON."""

    def __init__(self) -> None:
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def load_topic(self, topic_key: str) -> list[dict[str, Any]]:
        if topic_key in self._cache:
            return self._cache[topic_key]
        meta = config.TOPICS[topic_key]
        path = config.DATA_DIR / meta["file"]
        if not path.exists():
            from services.task_bank import ensure_task_files
            ensure_task_files()
        if not path.exists():
            logger.error("Task file not found: %s", path)
            return []
        with open(path, encoding="utf-8") as f:
            tasks: list[dict[str, Any]] = json.load(f)
        tasks.sort(key=lambda t: (t.get("difficulty", 1), t.get("id", "")))
        self._cache[topic_key] = tasks
        return tasks

    def get_task(self, topic: str, index: int) -> Optional[dict[str, Any]]:
        tasks = self.load_topic(topic)
        if 0 <= index < len(tasks):
            return tasks[index]
        return None

    def topic_title(self, topic_key: str) -> str:
        return config.TOPICS[topic_key]["title"]

    def topic_emoji(self, topic_key: str) -> str:
        return config.TOPICS[topic_key]["emoji"]

    def check_answer(self, user_answer: str, correct_answer: str) -> bool:
        return answers_equal(user_answer, correct_answer)

    def count_tasks(self, topic: str) -> int:
        return len(self.load_topic(topic))

    def sync_tasks_to_db(self, db: Any, topic: str) -> None:
        """Кэширует задачи в таблице tasks."""
        for task in self.load_topic(topic):
            db.upsert_task(task, topic)
