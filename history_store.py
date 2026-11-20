"""生成履歴をローカルの JSON ファイルに保存・読み込みするモジュール。

データベースは使わず、プロジェクト直下の history.json に保存する。
"""

import json
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "history.json"
MAX_ITEMS = 100  # これより古い履歴は捨てる


def load() -> list[dict]:
    """保存済みの履歴を新しい順で返す。ファイルがない・壊れている場合は空。"""
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def save(history: list[dict]) -> None:
    """履歴（新しい順）を保存する。"""
    HISTORY_FILE.write_text(
        json.dumps(history[:MAX_ITEMS], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear() -> None:
    HISTORY_FILE.unlink(missing_ok=True)
