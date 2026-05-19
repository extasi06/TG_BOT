"""CLI: генерация JSON-файлов задач."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.task_bank import BUILDERS, ensure_task_files  # noqa: E402
import config  # noqa: E402
import json  # noqa: E402


def main() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, builder in BUILDERS.items():
        path = config.DATA_DIR / filename
        tasks = builder()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(tasks)} tasks to {path}")


if __name__ == "__main__":
    main()
