"""hooks/record_read.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks.record_read import record_read


@pytest.fixture
def rule_env(
    hook_env: dict[str, str],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
) -> tuple[dict[str, str], Path]:
    """ルールのファイル 1 つを載せた索引を指す環境変数と、そのルールのパスを返す。"""
    rule = rule_file("python.md")
    index = make_index(index_text(str(rule), paths=["**/*.py"]))
    return {**hook_env, "RULE_INJECT_INDEXES_PROJECT": str(index)}, rule


def test_record_read_when_read_tool(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """Read で読んだルールを記録する（正常系）。"""
    # 準備
    env, rule = rule_env
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]


def test_record_read_when_bash(
    tmp_path: Path,
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
) -> None:
    """cat で読んだルールを記録する（正常系）。"""
    # 準備
    env, rule = rule_env
    payload = hook_payload(
        "PostToolUse",
        tool_name="Bash",
        tool_input={"command": "cat rules/python.md"},
        cwd=tmp_path,
    )
    # 実行
    record_read(payload, env)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]


def test_record_read_when_not_rule(
    tmp_path: Path,
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
) -> None:
    """ルールでないパスは記録しない（正常系）。"""
    # 準備
    env, _ = rule_env
    other = tmp_path / "other.md"
    other.write_text("# other\n", encoding="utf-8")
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(other)})
    # 実行
    record_read(payload, env)
    # 検証
    assert not (state_dir / f"{session_id}.txt").exists()


def test_record_read_when_unwritable(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    unwritable: Callable[[Path, int], Path],
) -> None:
    """書けないとき理由を返す（正常系）。"""
    # 準備
    env, rule = rule_env
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    result = record_read(payload, env)
    # 検証
    context = result["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert "PermissionError" in context
