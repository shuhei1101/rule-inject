"""既読の記録の破棄（PreCompact フック）の結合テスト。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
) -> None:
    """そのセッションの記録ファイルだけを消す（正常系）。"""
    # 準備
    target = write_record(["/r/a.md"])
    other = write_record(["/r/b.md"], "other-session")
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    completed = run_hook("discard_read", payload)
    # 検証
    assert not target.exists()
    assert other.exists()
    assert completed.returncode == 0


def test_normal_when_no_record(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """記録ファイルが無いセッションでも正常に終える（正常系）。"""
    # 準備
    payload = hook_payload("PreCompact", trigger="auto")
    # 実行
    completed = run_hook("discard_read", payload)
    # 検証
    assert completed.returncode == 0


def test_error_when_record_undeletable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
    state_dir: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録ファイルを消せないとき、圧縮は止めずにログと標準エラー出力に書く（異常系）。"""
    # 準備
    record_file = write_record(["/r/a.md"])
    unwritable(state_dir, 0o555)
    payload = hook_payload("PreCompact", trigger="manual")
    # 実行
    completed = run_hook("discard_read", payload)
    # 検証
    assert completed.stdout == ""
    assert '"operation": "delete_record"' in completed.stderr
    assert record_file.exists()
    assert completed.returncode == 0
