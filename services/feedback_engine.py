"""Формирование обратной связи из шаблонов и подбор аналогичных задач."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import config
from services.error_classifier import ClassificationResult, ErrorClassifier
from services.feedback_templates import get_template
from services.task_service import TaskService
from utils.markdown import escape_markdown


@dataclass
class FeedbackPackage:
    error_type: str
    classification: ClassificationResult
    message: str
    similar_task_index: Optional[int]
    is_repeat_error: bool
    repeat_count: int


class FeedbackEngine:
    """Модуль проверки и педагогической обратной связи без внешнего API."""

    def __init__(self, task_service: TaskService) -> None:
        self.task_service = task_service
        self.classifier = ErrorClassifier()

    def classify(
        self, task: dict[str, Any], user_answer: str, topic: str
    ) -> ClassificationResult:
        return self.classifier.classify(task, user_answer, topic)

    def find_similar_task_index(
        self,
        topic: str,
        current_index: int,
        task: dict[str, Any],
        error_type: str,
    ) -> Optional[int]:
        """Задача той же сложности с пересекающимся типом ошибки."""
        tasks = self.task_service.load_topic(topic)
        diff = task["difficulty"]
        patterns = set(task.get("error_patterns", []))
        candidates: list[int] = []
        for i, t in enumerate(tasks):
            if i == current_index:
                continue
            if t["difficulty"] != diff:
                continue
            t_patterns = set(t.get("error_patterns", []))
            if error_type in t_patterns or patterns & t_patterns:
                candidates.append(i)
        if candidates:
            return candidates[0]
        for i, t in enumerate(tasks):
            if i != current_index and t["difficulty"] == diff:
                return i
        return None

    def build_feedback(
        self,
        *,
        task: dict[str, Any],
        user_answer: str,
        topic: str,
        current_index: int,
        repeat_count: int,
        improvement_hint: Optional[str] = None,
    ) -> FeedbackPackage:
        classification = self.classify(task, user_answer, topic)
        error_type = classification.error_type
        tpl = get_template(error_type)
        label = config.ERROR_LABELS.get(error_type, error_type)
        similar_idx = self.find_similar_task_index(topic, current_index, task, error_type)

        repeat_block = ""
        if repeat_count > 1:
            repeat_block = (
                f"\n\n⚠️ *Повтор ошибки* ({repeat_count}-й раз): «{label}».\n"
                "Сконцентрируйся на правиле ниже, затем попробуй аналогичную задачу."
            )
        elif repeat_count == 1:
            repeat_block = "\n\n📌 Зафиксировали тип ошибки — после подсказки закрепи на похожей задаче."

        improvement_block = ""
        if improvement_hint:
            improvement_block = f"\n\n📈 *Прогресс:* {improvement_hint}"

        similar_block = ""
        if similar_idx is not None:
            similar_block = (
                "\n\n🔁 Нажми «Аналогичная задача», чтобы закрепить навык "
                "без перехода к более сложным заданиям."
            )

        message = (
            f"❌ *Разбор ошибки*\n"
            f"Тип: *{tpl['title']}* ({label})\n"
            f"_Уверенность классификатора: {int(classification.confidence * 100)}%_\n"
            f"{repeat_block}{improvement_block}\n\n"
            f"📖 *Правило:*\n{tpl['rule']}\n\n"
            f"🧭 *Направление:*\n{tpl['direction']}\n\n"
            f"💭 *Подумай:* {tpl['reflection']}\n\n"
            f"💡 *Подсказка к задаче:*\n{escape_markdown(task.get('hint', ''))}\n\n"
            f"_{tpl['quality_note']}_"
            f"{similar_block}"
        )

        return FeedbackPackage(
            error_type=error_type,
            classification=classification,
            message=message,
            similar_task_index=similar_idx,
            is_repeat_error=repeat_count > 1,
            repeat_count=repeat_count,
        )
