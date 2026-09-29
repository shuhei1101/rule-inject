"""既読の記録（PostToolUse フック）の結合テスト。"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def rule_index(
    rule_file: Callable[..., Path],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
) -> tuple[Path, Path]:
    """ルールのファイル 1 つを載せた索引と、そのルールのパスを返す。"""
    rule = rule_file("python.md")
    index = make_index(index_text({"rule": str(rule), "paths": ["**/*.py"]}))
    return index, rule


def test_normal_when_read_by_read_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """Read で読んだルールの場所を記録する（正常系）。"""
    # 準備
    index, rule = rule_index
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    assert completed.returncode == 0


def test_normal_when_read_by_bash(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """Bash の読むコマンドの引数にあるルールの場所を記録する（正常系）。"""
    # 準備
    index, rule = rule_index
    payload = hook_payload(
        "PostToolUse",
        tool_name="Bash",
        tool_input={"command": "cat rules/python.md"},
        cwd=tmp_path,
    )
    # 実行
    run_hook("record_read", payload, index=index)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]


def test_normal_when_not_rule(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    session_id: str,
) -> None:
    """索引に載っていないパスを読んでも記録しない（正常系）。"""
    # 準備
    index, _ = rule_index
    other = tmp_path / "other.md"
    other.write_text("# other\n", encoding="utf-8")
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(other)})
    # 実行
    run_hook("record_read", payload, index=index)
    # 検証
    assert not (state_dir / f"{session_id}.txt").exists()


def test_error_when_record_unwritable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    log_folder: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録のフォルダに書けないとき、既読にできなかった理由を載せる（異常系）。"""
    # 準備
    index, rule = rule_index
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert "PermissionError" in context
    assert '"operation": "write_record"' in completed.stderr
    assert completed.returncode == 0
