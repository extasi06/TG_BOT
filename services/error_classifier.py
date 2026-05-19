"""Классификатор типовых ошибок: правила + разбор выражений."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import config
from utils.expression_parser import (
    extract_expression_from_question,
    numeric_value,
    try_evaluate_expression,
    try_evaluate_left_to_right,
    values_close,
)
from utils.validators import normalize_answer, try_parse_fraction


@dataclass
class ClassificationResult:
    error_type: str
    confidence: float  # 0..1
    reason: str
    detected_by: str  # rule | expression | pattern


class ErrorClassifier:
    """Смешанный подход: шаблоны задачи + эвристики + разбор выражения."""

    def classify(
        self,
        task: dict[str, Any],
        user_answer: str,
        topic: str,
    ) -> ClassificationResult:
        patterns: list[str] = list(task.get("error_patterns") or [])
        u = normalize_answer(user_answer)
        correct = normalize_answer(task["answer"])
        question = task.get("question", "")

        user_val = numeric_value(user_answer)
        correct_val = numeric_value(task["answer"])

        # --- Анализ выражения в условии (арифметика / дроби) ---
        expr = extract_expression_from_question(question)
        if expr:
            pemdas = try_evaluate_expression(expr)
            ltr = try_evaluate_left_to_right(expr)
            if (
                pemdas is not None
                and ltr is not None
                and not values_close(pemdas, ltr)
                and user_val is not None
                and values_close(user_val, ltr)
                and "order_of_operations" in patterns
            ):
                return ClassificationResult(
                    "order_of_operations",
                    0.9,
                    "Ответ совпадает с вычислением слева направо, а не по правилам приоритета.",
                    "expression",
                )

        # --- Знак ---
        if user_val is not None and correct_val is not None:
            if user_val * correct_val < 0 and abs(user_val) == abs(correct_val):
                return ClassificationResult(
                    "sign_error",
                    0.85,
                    "Численное значение совпало по модулю, но знак неверный.",
                    "rule",
                )

        # --- Сложили только числители ---
        if "/" in correct and self._added_numerators_only(question, user_answer):
            return ClassificationResult(
                "added_numerators_only",
                0.88,
                "Похоже, сложены только числители без общего знаменателя.",
                "rule",
            )

        # --- Неверный знаменатель ---
        if "/" in u and "/" in correct:
            wrong_denom = self._wrong_denominator(user_answer, task["answer"])
            if wrong_denom and "wrong_common_denominator" in patterns:
                return ClassificationResult(
                    "wrong_common_denominator",
                    0.8,
                    "Знаменатель в ответе не совпадает с требуемым после приведения.",
                    "rule",
                )

        # --- Дробь vs число ---
        if "/" in correct and "/" not in u and "fraction_addition" in patterns:
            return ClassificationResult(
                "fraction_addition",
                0.75,
                "Ответ дан целым/десятичным числом, ожидалась дробь.",
                "pattern",
            )

        if "×" in question or "*" in question or "÷" in question or "/" in question:
            if "/" not in u and "/" in correct and "fraction_multiplication" in patterns:
                if "×" in question or "*" in question:
                    return ClassificationResult(
                        "fraction_multiplication",
                        0.7,
                        "Возможно, применено сложение вместо умножения дробей.",
                        "pattern",
                    )

        # --- Текстовые: малое число при большом ответе ---
        if topic == "word_problems" and user_val is not None and correct_val is not None:
            if correct_val > 50 and user_val < 10 and "misread_condition" in patterns:
                return ClassificationResult(
                    "misread_condition",
                    0.72,
                    "Ответ слишком мал для масштаба задачи — проверь условие.",
                    "rule",
                )
            if "unit_conversion" in patterns and self._unit_mismatch(user_val, correct_val):
                return ClassificationResult(
                    "unit_conversion",
                    0.7,
                    "Ответ отличается примерно в 10/60/100 раз — возможна ошибка единиц.",
                    "rule",
                )

        # --- Проценты ---
        if "%" in question and "percent_error" in patterns:
            return ClassificationResult(
                "percent_error",
                0.8,
                "Похоже, неверно перевели процент в часть от числа.",
                "rule",
            )

        # --- Близкий, но неверный ответ ---
        if user_val is not None and correct_val is not None:
            if abs(user_val - correct_val) <= max(1.0, abs(correct_val) * 0.05):
                return ClassificationResult(
                    "calculation_error",
                    0.65,
                    "Ответ близок к верному — вероятна ошибка в одном шаге.",
                    "rule",
                )

        # --- Первый паттерн из задачи ---
        if patterns:
            return ClassificationResult(
                patterns[0],
                0.55,
                f"Типовая ошибка по банку задачи: {config.ERROR_LABELS.get(patterns[0], patterns[0])}.",
                "pattern",
            )

        return ClassificationResult(
            "calculation_error",
            0.5,
            "Не удалось уточнить тип — общая арифметическая проверка.",
            "rule",
        )

    def _added_numerators_only(self, question: str, user_answer: str) -> bool:
        nums = re.findall(r"(\d+)\s*/\s*(\d+)", question)
        if len(nums) < 2 or "+" not in question:
            return False
        try:
            sum_num = sum(int(n) for n, _ in nums)
            user_v = numeric_value(user_answer)
            return user_v is not None and abs(user_v - sum_num) < 1e-6
        except ValueError:
            return False

    def _wrong_denominator(self, user_answer: str, correct_answer: str) -> bool:
        u_frac = try_parse_fraction(user_answer)
        c_frac = try_parse_fraction(correct_answer)
        if u_frac is None or c_frac is None:
            return False
        return u_frac.denominator != c_frac.denominator and u_frac.numerator == c_frac.numerator

    def _unit_mismatch(self, user_val: float, correct_val: float) -> bool:
        if correct_val == 0:
            return False
        ratio = user_val / correct_val
        for factor in (10, 60, 100, 1000, 0.1, 1 / 60, 0.01):
            if 0.85 < ratio / factor < 1.15:
                return True
        return False
