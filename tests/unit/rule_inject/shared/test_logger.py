"""shared/logger.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rule_inject.shared.logger import Component, LogOperation, write_log


def _fixed_now() -> datetime:
    """固定の UTC の時刻を返す。"""
    return datetime(2026, 9, 29, 8, 0, 0, tzinfo=UTC)


def test_write_log(
    tmp_path: Path,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """ログに 1 行追記する（正常系）。"""
    # 準備
    state = tmp_path / "state"
    # 実行
    write_log(
        state,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        session_id="s1",
        path="/p/state",
        now=_fixed_now,
    )
    # 検証
    lines = read_lines(state / "rule-inject.log")
    assert len(lines) == 1
    assert json.loads(lines[0]) == {
        "time": "2026-09-29T08:00:00+00:00",
        "component": "read_rules",
        "session_id": "s1",
        "operation": "write_record",
        "path": "/p/state",
        "reason": "PermissionError: denied",
    }


def test_write_log_when_unwritable(
    tmp_path: Path,
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """書けないとき標準エラー出力へ出す（異常系）。"""
    # 準備
    state = tmp_path / "state"
    state.mkdir()
    unwritable(state, 0o555)
    # 実行
    write_log(
        state,
        component=Component("read_rules"),
        operation=LogOperation("write_record"),
        reason="PermissionError: denied",
        now=_fixed_now,
    )
    # 検証
    captured = capsys.readouterr()
    assert json.loads(captured.err.strip())["operation"] == "write_record"
