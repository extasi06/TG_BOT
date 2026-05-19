"""Однократное создание JSON-файлов в data/ (запуск: python create_data.py)."""

from services.task_bank import BUILDERS
import config
import json

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
for filename, builder in BUILDERS.items():
    path = config.DATA_DIR / filename
    tasks = builder()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"{path}: {len(tasks)} tasks")
