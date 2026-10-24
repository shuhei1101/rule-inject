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
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """Read で読んだルールの場所を記録する（正常系）。"""
    # 準備
    index, rule = rule_index
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "read"
    assert history[0]["tool"] == "Read"
    assert history[0]["location"] == str(rule)
    assert completed.returncode == 0


def test_normal_when_read_by_bash(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
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
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "bash"
    assert history[0]["tool"] == "Bash"


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
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


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


def test_normal_when_read_by_mcp_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """`read_by` に当たった MCP のツールの呼び出しのエントリのルールの場所を記録する（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = make_index(
        index_text(
            {
                "rule": str(rule),
                "read_by": [{"tools": ["mcp__docs__get_doc"], "args": {"id": ["python"]}}],
            }
        )
    )
    payload = hook_payload(
        "PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "python"}
    )
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["tool"] == "mcp__docs__get_doc"
    assert history[0]["location"] == str(rule)
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_read_by_not_matched(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    state_dir: Path,
    session_id: str,
) -> None:
    """`read_by` の引数に当たらない呼び出しと、案内用の `tools` だけに当たる呼び出しでは記録しない（正常系）。"""
    # 準備
    read_by_rule = rule_file("read_by.md")
    guide_rule = rule_file("guide.md")
    index = make_index(
        index_text(
            {
                "rule": str(read_by_rule),
                "read_by": [{"tools": ["mcp__docs__get_doc"], "args": {"id": ["python"]}}],
            },
            {"rule": str(guide_rule), "tools": ["mcp__docs__get_doc"]},
        )
    )
    payload = hook_payload(
        "PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "typescript"}
    )
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()
    assert completed.returncode == 0


def test_normal_when_own_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    state_dir: Path,
    session_id: str,
) -> None:
    """このプラグイン自身の MCP のツールの呼び出しは、`read_by` に当たっても記録しない（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = make_index(
        index_text(
            {
                "rule": str(rule),
                "read_by": [{"tools": ["mcp__plugin_rule-inject_rule-inject__*"]}],
            }
        )
    )
    payload = hook_payload(
        "PostToolUse",
        tool_name="mcp__plugin_rule-inject_rule-inject__read_rules",
        tool_input={"locations": [str(rule)]},
    )
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()
    assert completed.returncode == 0


def test_error_when_history_unwritable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    rule_index: tuple[Path, Path],
    state_dir: Path,
    log_folder: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """既読の履歴に書けないとき、既読にはしたうえで書けなかった理由を載せる（異常系）。"""
    # 準備
    index, rule = rule_index
    (state_dir / f"{session_id}.history.jsonl").mkdir(parents=True)
    log_folder.mkdir()
    unwritable(log_folder, 0o555)
    payload = hook_payload("PostToolUse", tool_name="Read", tool_input={"file_path": str(rule)})
    # 実行
    completed = run_hook("record_read", payload, index=index)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert "IsADirectoryError" in context
    assert '"operation": "write_history"' in completed.stderr
    assert completed.returncode == 0
