"""Безопасный разбор и вычисление простых математических выражений."""

from __future__ import annotations

import ast
import operator
import re
from fractions import Fraction
from typing import Optional

from utils.validators import normalize_answer, try_parse_fraction

# Допустимые операции для eval через AST
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _normalize_expr(expr: str) -> str:
    s = expr.strip().lower()
    s = s.replace("×", "*").replace("÷", "/").replace("−", "-")
    s = s.replace(",", ".")
    s = re.sub(r"\s+", "", s)
    return s


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
        return _OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError
        return float(_OPS[type(node.op)](left, right))
    raise ValueError("Unsupported expression")


def try_evaluate_expression(expr: str) -> Optional[float]:
    """Вычисляет выражение вида 2+3*4 (без функций и переменных)."""
    s = _normalize_expr(expr)
    if not s or not re.match(r"^[\d.+\-*/()]+$", s):
        return None
    try:
        tree = ast.parse(s, mode="eval")
        return _safe_eval(tree.body)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
        return None


def try_evaluate_left_to_right(expr: str) -> Optional[float]:
    """Упрощённый порядок слева направо (+, -, *, /) — для детекции типовой ошибки."""
    s = _normalize_expr(expr)
    if not re.match(r"^[\d.+\-*/]+$", s):
        return None
    tokens = re.findall(r"[\d.]+|[+\-*/]", s)
    if not tokens or not re.match(r"^[\d.]", tokens[0]):
        return None
    try:
        acc = float(tokens[0])
    except ValueError:
        return None
    i = 1
    while i + 1 < len(tokens):
        op, num = tokens[i], tokens[i + 1]
        try:
            val = float(num)
        except ValueError:
            return None
        if op == "+":
            acc += val
        elif op == "-":
            acc -= val
        elif op == "*":
            acc *= val
        elif op == "/":
            if val == 0:
                return None
            acc /= val
        else:
            return None
        i += 2
    return acc


def extract_expression_from_question(question: str) -> Optional[str]:
    """Извлекает вычислимую часть из условия задачи."""
    q = question.strip()
    # Убрать префиксы
    for prefix in ("Вычисли:", "Вычисли", "Реши:", "Найди значение:"):
        if q.lower().startswith(prefix.lower()):
            q = q[len(prefix) :].strip()
    # Скобки в начале
    m = re.search(r"([\d./\s+\-×÷*()]+)", q)
    if m:
        candidate = m.group(1).strip()
        if re.search(r"[\d]", candidate) and re.search(r"[+\-*/×÷]", candidate):
            return candidate
    if re.match(r"^[\d./\s+\-×÷*()]+$", q.replace(" ", "")):
        return q
    return None


def numeric_value(text: str) -> Optional[float]:
    frac = try_parse_fraction(text)
    if frac is not None:
        return float(frac)
    try:
        return float(normalize_answer(text))
    except ValueError:
        return None


def values_close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol
