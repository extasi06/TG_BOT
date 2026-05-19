"""Слой доступа к SQLite."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    current_topic TEXT,
    level INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    current_task_id TEXT,
    current_difficulty INTEGER DEFAULT 1,
    task_index INTEGER DEFAULT 0,
    hints_used_session INTEGER DEFAULT 0,
    task_started_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    hint TEXT,
    explanation TEXT,
    error_patterns TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    user_answer TEXT,
    is_correct INTEGER NOT NULL,
    difficulty INTEGER,
    time_spent_sec REAL,
    error_type TEXT,
    used_hint INTEGER DEFAULT 0,
    xp_earned INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE IF NOT EXISTS statistics (
    user_id INTEGER PRIMARY KEY,
    total_attempts INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    hints_count INTEGER DEFAULT 0,
    total_time_sec REAL DEFAULT 0,
    popular_errors TEXT DEFAULT '{}',
    no_hint_streak INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    earned_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, code)
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS error_learning (
    user_id INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    times_seen INTEGER DEFAULT 0,
    times_repeated INTEGER DEFAULT 0,
    feedback_shown INTEGER DEFAULT 0,
    attempts_after_feedback INTEGER DEFAULT 0,
    correct_after_feedback INTEGER DEFAULT 0,
    similar_attempts INTEGER DEFAULT 0,
    similar_correct INTEGER DEFAULT 0,
    last_feedback_at TEXT,
    PRIMARY KEY (user_id, error_type)
);

CREATE TABLE IF NOT EXISTS feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    error_type TEXT NOT NULL,
    user_answer TEXT,
    is_repeat_error INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


class Database:
    """Обёртка над SQLite для бота."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate(conn)
        logger.info("Database schema initialized at %s", self.db_path)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """Добавляет новые колонки в существующую БД."""
        user_cols = [
            "ALTER TABLE users ADD COLUMN last_error_type TEXT",
            "ALTER TABLE users ADD COLUMN active_feedback_error TEXT",
            "ALTER TABLE users ADD COLUMN similar_practice_mode INTEGER DEFAULT 0",
        ]
        attempt_cols = [
            "ALTER TABLE attempts ADD COLUMN is_similar_practice INTEGER DEFAULT 0",
            "ALTER TABLE attempts ADD COLUMN after_feedback INTEGER DEFAULT 0",
            "ALTER TABLE attempts ADD COLUMN feedback_error_type TEXT",
        ]
        for sql in user_cols + attempt_cols:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass

    def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
    ) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return dict(row)
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
                """,
                (user_id, username, first_name),
            )
            conn.execute(
                "INSERT OR IGNORE INTO statistics (user_id) VALUES (?)",
                (user_id,),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row)

    def update_user(self, user_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [user_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE users SET {cols} WHERE user_id = ?", values)

    def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_task(self, task: dict[str, Any], topic: str) -> None:
        patterns = json.dumps(task.get("error_patterns", []), ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks
                (id, topic, question, answer, difficulty, hint, explanation, error_patterns)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["id"],
                    topic,
                    task["question"],
                    task["answer"],
                    task["difficulty"],
                    task.get("hint", ""),
                    task.get("explanation", ""),
                    patterns,
                ),
            )

    def record_attempt(
        self,
        user_id: int,
        task_id: str,
        user_answer: str,
        is_correct: bool,
        difficulty: int,
        time_spent_sec: float,
        error_type: Optional[str],
        used_hint: bool,
        xp_earned: int,
        *,
        is_similar_practice: bool = False,
        after_feedback: bool = False,
        feedback_error_type: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO attempts
                (user_id, task_id, user_answer, is_correct, difficulty,
                 time_spent_sec, error_type, used_hint, xp_earned,
                 is_similar_practice, after_feedback, feedback_error_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    task_id,
                    user_answer,
                    int(is_correct),
                    difficulty,
                    time_spent_sec,
                    error_type,
                    int(used_hint),
                    xp_earned,
                    int(is_similar_practice),
                    int(after_feedback),
                    feedback_error_type,
                ),
            )

    def get_statistics(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM statistics WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                return dict(row)
            conn.execute(
                "INSERT INTO statistics (user_id) VALUES (?)", (user_id,)
            )
            row = conn.execute(
                "SELECT * FROM statistics WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row)

    def update_statistics(
        self,
        user_id: int,
        *,
        is_correct: bool,
        time_spent_sec: float,
        error_type: Optional[str],
        used_hint: bool,
    ) -> dict[str, Any]:
        stats = self.get_statistics(user_id)
        total = stats["total_attempts"] + 1
        correct = stats["correct_count"] + (1 if is_correct else 0)
        wrong = stats["wrong_count"] + (0 if is_correct else 1)
        hints = stats["hints_count"] + (1 if used_hint else 0)
        total_time = stats["total_time_sec"] + time_spent_sec

        popular: dict[str, int] = json.loads(stats.get("popular_errors") or "{}")
        if error_type and not is_correct:
            popular[error_type] = popular.get(error_type, 0) + 1

        no_hint_streak = stats.get("no_hint_streak", 0)
        if is_correct and not used_hint:
            no_hint_streak += 1
        else:
            no_hint_streak = 0

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE statistics SET
                    total_attempts = ?,
                    correct_count = ?,
                    wrong_count = ?,
                    hints_count = ?,
                    total_time_sec = ?,
                    popular_errors = ?,
                    no_hint_streak = ?
                WHERE user_id = ?
                """,
                (
                    total,
                    correct,
                    wrong,
                    hints,
                    total_time,
                    json.dumps(popular, ensure_ascii=False),
                    no_hint_streak,
                    user_id,
                ),
            )
        return self.get_statistics(user_id)

    def add_achievement(self, user_id: int, code: str) -> bool:
        """Возвращает True, если достижение новое."""
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO achievements (user_id, code) VALUES (?, ?)",
                    (user_id, code),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_achievements(self, user_id: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT code FROM achievements WHERE user_id = ? ORDER BY earned_at",
                (user_id,),
            ).fetchall()
            return [r["code"] for r in rows]

    def save_feedback(self, user_id: int, message: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO feedback (user_id, message) VALUES (?, ?)",
                (user_id, message),
            )

    def record_error_learning(self, user_id: int, error_type: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM error_learning WHERE user_id = ? AND error_type = ?",
                (user_id, error_type),
            ).fetchone()
            if row:
                times_seen = row["times_seen"] + 1
                times_repeated = row["times_repeated"] + (1 if times_seen > 1 else 0)
                conn.execute(
                    """
                    UPDATE error_learning SET times_seen = ?, times_repeated = ?
                    WHERE user_id = ? AND error_type = ?
                    """,
                    (times_seen, times_repeated, user_id, error_type),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO error_learning (user_id, error_type, times_seen)
                    VALUES (?, ?, 1)
                    """,
                    (user_id, error_type),
                )
        return self.get_error_learning(user_id, error_type)

    def get_error_learning(self, user_id: int, error_type: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM error_learning WHERE user_id = ? AND error_type = ?",
                (user_id, error_type),
            ).fetchone()
            return dict(row) if row else {"times_seen": 0, "times_repeated": 0}

    def get_all_error_learning(self, user_id: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM error_learning WHERE user_id = ? ORDER BY times_seen DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def log_feedback(
        self,
        user_id: int,
        task_id: str,
        error_type: str,
        user_answer: str,
        is_repeat: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feedback_log (user_id, task_id, error_type, user_answer, is_repeat_error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, task_id, error_type, user_answer, is_repeat),
            )

    def mark_feedback_shown(self, user_id: int, error_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE error_learning SET feedback_shown = feedback_shown + 1,
                    last_feedback_at = datetime('now')
                WHERE user_id = ? AND error_type = ?
                """,
                (user_id, error_type),
            )

    def record_correct_after_feedback(self, user_id: int, error_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE error_learning SET
                    attempts_after_feedback = attempts_after_feedback + 1,
                    correct_after_feedback = correct_after_feedback + 1
                WHERE user_id = ? AND error_type = ?
                """,
                (user_id, error_type),
            )

    def record_error_repeat(self, user_id: int, error_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE error_learning SET
                    attempts_after_feedback = attempts_after_feedback + 1,
                    times_repeated = times_repeated + 1
                WHERE user_id = ? AND error_type = ?
                """,
                (user_id, error_type),
            )

    def increment_similar_attempts(self, user_id: int, error_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE error_learning SET similar_attempts = similar_attempts + 1
                WHERE user_id = ? AND error_type = ?
                """,
                (user_id, error_type),
            )

    def record_similar_success(self, user_id: int, error_type: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE error_learning SET
                    similar_correct = similar_correct + 1,
                    attempts_after_feedback = attempts_after_feedback + 1,
                    correct_after_feedback = correct_after_feedback + 1
                WHERE user_id = ? AND error_type = ?
                """,
                (user_id, error_type),
            )

    def get_aprobation_summary(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            learning = conn.execute(
                """
                SELECT SUM(times_seen) AS total_errors,
                       SUM(times_repeated) AS total_repeats,
                       SUM(attempts_after_feedback) AS after_fb,
                       SUM(correct_after_feedback) AS correct_after,
                       SUM(similar_attempts) AS sim_att,
                       SUM(similar_correct) AS sim_ok
                FROM error_learning WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            d = dict(learning) if learning else {}
            after = d.get("after_fb") or 0
            correct = d.get("correct_after") or 0
            sim_a = d.get("sim_att") or 0
            sim_c = d.get("sim_ok") or 0
            return {
                **d,
                "after_feedback_success_pct": round(100 * correct / after, 1) if after else 0,
                "similar_success_pct": round(100 * sim_c / sim_a, 1) if sim_a else 0,
            }

    def get_global_stats_summary(self, user_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            attempts = conn.execute(
                """
                SELECT COUNT(*) AS cnt,
                       SUM(is_correct) AS correct,
                       AVG(time_spent_sec) AS avg_time
                FROM attempts WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            by_difficulty = conn.execute(
                """
                SELECT difficulty,
                       COUNT(*) AS total,
                       SUM(is_correct) AS correct
                FROM attempts WHERE user_id = ?
                GROUP BY difficulty ORDER BY difficulty
                """,
                (user_id,),
            ).fetchall()
            return {
                "attempts": dict(attempts) if attempts else {},
                "by_difficulty": [dict(r) for r in by_difficulty],
            }

    def get_solved_task_ids(self, user_id: int, topic: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT a.task_id
                FROM attempts a
                JOIN tasks t ON t.id = a.task_id
                WHERE a.user_id = ? AND a.is_correct = 1 AND t.topic = ?
                """,
                (user_id, topic),
            ).fetchall()
            return [row[0] for row in rows]
