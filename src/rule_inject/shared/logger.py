"""失敗した操作をログ（JSON Lines）へ書く。"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

LOG_FILE_NAME = "rule-inject.log"


class Component(StrEnum):
    """ログの `component` の値（インターフェース定義の識別子）。"""

    RULE_GUIDE = "rule_guide"
    SESSION_ID_INJECTION = "session_id_injection"
    RECORD_READ = "record_read"
    DISCARD_READ = "discard_read"
    WORK_RULES = "work_rules"
    READ_RULES = "read_rules"


class LogOperation(StrEnum):
    """ログの `operation` の値（失敗した操作）。"""

    READ_INDEX = "read_index"
    READ_RECORD = "read_record"
    WRITE_RECORD = "write_record"
    DELETE_RECORD = "delete_record"
    UNEXPECTED = "unexpected"


def _utc_now() -> datetime:
    """現在の UTC の時刻を返す。"""
    return datetime.now(UTC)


def write_log(
    state_dir: Path,
    *,
    component: Component,
    operation: LogOperation,
    reason: str,
    session_id: str | None = None,
    path: str | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> None:
    """失敗した操作をログに 1 行追記し、書けないときは標準エラー出力へ出す。"""
    # ER 図「ログ」の列を持つ 1 行の JSON にする
    line = json.dumps(
        {
            "time": now().isoformat(),
            "component": component.value,
            "session_id": session_id,
            "operation": operation.value,
            "path": path,
            "reason": reason,
        },
        ensure_ascii=False,
    )
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / LOG_FILE_NAME).open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
    except OSError:
        # フックの標準出力は JSON 専用のため、ログに書けない失敗は標準エラー出力へ逃がす
        print(line, file=sys.stderr)
