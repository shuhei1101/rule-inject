"""hooks/sweep_read.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks.sweep_read import sweep_read


def test_sweep_read(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """保持期間を過ぎた記録を消す（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert not expired.exists()


def test_sweep_read_when_invalid_session_id(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_aged_record: Callable[..., Path],
) -> None:
    """session_id の形が外れていれば何も消さない（正常系）。"""
    # 準備
    expired = write_aged_record("expired-session", 31)
    payload = hook_payload("SessionStart", source="startup", session_id="../x")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    assert expired.exists()


def test_sweep_read_when_undeletable(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    write_aged_record: Callable[..., Path],
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """消せず、ログにも書けないとき標準エラー出力に書く（正常系）。"""
    # 準備
    write_aged_record("expired-session", 31)
    unwritable(state_dir, 0o555)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    result = sweep_read(payload, hook_env)
    # 検証
    assert result is None
    entry = json.loads(capsys.readouterr().err)
    assert entry["component"] == "sweep_read"
    assert entry["operation"] == "delete_record"
