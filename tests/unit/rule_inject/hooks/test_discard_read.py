"""hooks/discard_read.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks.discard_read import discard_read


def test_discard_read(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """記録を削除する（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    result = discard_read(payload, hook_env)
    # 検証
    assert result is None
    assert not record_file.exists()


def test_discard_read_when_undeletable(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    log_folder: Path,
    write_record: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """削除できないときログに書く（正常系）。"""
    # 準備
    write_record(["/r/a.md"])
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    result = discard_read(payload, hook_env)
    # 検証
    assert result is None
    assert "delete_record" in capsys.readouterr().err


def test_discard_read_when_guided(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
    write_guided: Callable[[Sequence[str]], Path],
) -> None:
    """案内済みの記録も削除する（正常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    guided_file = write_guided(["/r/b.md"])
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    result = discard_read(payload, hook_env)
    # 検証
    assert result is None
    assert not record_file.exists()
    assert not guided_file.exists()


def test_discard_read_when_settings_unreadable(
    xdg_state_home: Path,
    session_id: str,
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めないときはログに書くだけで何も削除しない（正常系）。"""
    # 準備
    env = unreadable_env("unknown_key")
    record_file = xdg_state_home / "rule-inject" / f"{session_id}.txt"
    record_file.parent.mkdir(parents=True)
    record_file.write_text("/r/a.md\n", encoding="utf-8")
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    result = discard_read(payload, env)
    # 検証
    assert result is None
    assert record_file.exists()
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
