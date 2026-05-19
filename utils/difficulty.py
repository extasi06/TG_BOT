"""Адаптивная сложность и расчёт уровня."""

from __future__ import annotations

import config


def difficulty_label(level: int) -> str:
    labels = {
        1: "очень лёгкая",
        2: "лёгкая",
        3: "средняя",
        4: "сложная",
        5: "очень сложная",
    }
    return labels.get(level, "средняя")


def calculate_xp(difficulty: int, used_hint: bool) -> int:
    base = config.XP_PER_DIFFICULTY.get(difficulty, 20)
    if used_hint:
        return max(1, int(base * config.XP_HINT_MULTIPLIER))
    return base


def level_from_xp(xp: int) -> int:
    return max(1, 1 + xp // config.LEVEL_XP_STEP)


def xp_to_next_level(xp: int) -> int:
    current_level = level_from_xp(xp)
    next_threshold = current_level * config.LEVEL_XP_STEP
    return max(0, next_threshold - xp)


def adapt_difficulty(
    current: int,
    streak: int,
    recent_wrong: int,
) -> int:
    """
    Повышает сложность после серии успехов,
    понижает после нескольких ошибок подряд.
    """
    new_level = current
    if streak >= 3 and new_level < 5:
        new_level += 1
    if recent_wrong >= 2 and new_level > 1:
        new_level -= 1
    return max(1, min(5, new_level))


def pick_task_index_for_difficulty(
    tasks: list[dict],
    target_difficulty: int,
    start_index: int,
) -> int:
    """Выбирает индекс задачи, ближайшей по сложности и позиции к start_index.

    Стратегия: минимизируем кортеж (abs(difficulty-target), abs(i-start_index)).
    Это сглаживает резкие перескоки по сложности и отдаёт предпочтение
    задачам рядом с текущим индексом.
    """
    if not tasks:
        return 0
    best_i = 0
    best_key = (abs(tasks[0]["difficulty"] - target_difficulty), abs(0 - start_index))
    for i, t in enumerate(tasks):
        key = (abs(t["difficulty"] - target_difficulty), abs(i - start_index))
        if key < best_key:
            best_key = key
            best_i = i
    return best_i
