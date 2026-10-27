"""hooks/record_read.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks._runner import SETTINGS_FAILURE_SUMMARY
from rule_inject.hooks.record_read import record_read

# 本文が `test` のルールの本文のハッシュ
HASH_TEST = "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def _read_response(start_line: Any, num_lines: Any, total_lines: Any) -> dict[str, Any]:
    """Read の `tool_response`（`file` に読んだ範囲を持つ）を作る。"""
    return {
        "type": "text",
        "file": {
            "filePath": "rule.md",
            "content": "test",
            "startLine": start_line,
            "numLines": num_lines,
            "totalLines": total_lines,
        },
    }


@pytest.fixture
def rule_env(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
) -> tuple[dict[str, str], Path]:
    """ルールのファイル 1 つ（本文は `test`）を載せた索引を指す環境変数と、そのルールのパスを返す。"""
    rule = rule_file("python.md", "test")
    index = make_index(index_text(str(rule), paths=["**/*.py"]))
    return settings_env(indexes=[str(index)]), rule


def test_record_read_when_read_tool(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """Read で読んだルールを記録する（正常系）。"""
    # 準備
    env, rule = rule_env
    payload = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": str(rule)},
        tool_response=_read_response(1, 3, 3),
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert read_lines(state_dir / f"{session_id}.txt") == [f"{rule}\t{HASH_TEST}"]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "read"
    assert history[0]["tool"] == "Read"
    assert history[0]["location"] == str(rule)


def test_record_read_when_bash(
    tmp_path: Path,
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
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
    assert read_lines(state_dir / f"{session_id}.txt") == [f"{rule}\t{HASH_TEST}"]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "bash"
    assert history[0]["tool"] == "Bash"
    assert history[0]["location"] == str(rule)


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
    payload = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": str(other)},
        tool_response=_read_response(1, 1, 1),
    )
    # 実行
    record_read(payload, env)
    # 検証
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


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
    payload = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": str(rule)},
        tool_response=_read_response(1, 3, 3),
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    context = result["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert "PermissionError" in context


def test_record_read_when_mcp_tool(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """`read_by` に当たった MCP のツールの呼び出しでルールを記録する（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    index = make_index(index_text(str(rule), read_by=[{"tools": ["mcp__docs__get_doc"]}]))
    env = settings_env(indexes=[str(index)])
    payload = hook_payload("PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "a"})
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert read_lines(state_dir / f"{session_id}.txt") == [f"{rule}\t{HASH_TEST}"]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["tool"] == "mcp__docs__get_doc"
    assert history[0]["location"] == str(rule)


def test_record_read_when_read_by_not_matched(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
) -> None:
    """`read_by` に当たらない MCP のツールは記録しない（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    index = make_index(index_text(str(rule), tools=["mcp__*"]))
    env = settings_env(indexes=[str(index)])
    payload = hook_payload("PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "a"})
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


def test_record_read_when_rule_is_url(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    log_folder: Path,
    session_id: str,
) -> None:
    """`rule` が URL のエントリは `read_by` に当たっても記録せず、知らせもしない（正常系）。"""
    # 準備
    index = make_index(
        index_text(
            "https://example.com/a.md",
            read_by=[{"tools": ["mcp__docs__get_doc"]}],
        )
    )
    env = settings_env(indexes=[str(index)])
    payload = hook_payload("PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "a"})
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()
    assert not log_folder.exists()


def test_record_read_when_history_unwritable(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """履歴に書けないとき既読を残して理由を返す（正常系）。"""
    # 準備
    env, rule = rule_env
    (state_dir / f"{session_id}.history.jsonl").mkdir(parents=True)
    payload = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": str(rule)},
        tool_response=_read_response(1, 3, 3),
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    assert read_lines(state_dir / f"{session_id}.txt") == [f"{rule}\t{HASH_TEST}"]
    context = result["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert "IsADirectoryError" in context
    log = read_daily_log()
    assert len(log) == 1
    assert log[0]["operation"] == "write_history"


def test_record_read_when_read_partially(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
) -> None:
    """Read で一部だけを読んだときは記録しない（正常系）。"""
    # 準備
    env, rule = rule_env
    tool_input = {"file_path": str(rule)}
    partial = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input=tool_input,
        tool_response=_read_response(5, 7, 11),
    )
    without_file = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input=tool_input,
        tool_response={"type": "text"},
    )
    string_start_line = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input=tool_input,
        tool_response=_read_response("1", 3, 3),
    )
    # 実行
    results = [record_read(payload, env) for payload in (partial, without_file, string_start_line)]
    # 検証
    assert results == [None, None, None]
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


def test_record_read_when_mcp_document(
    tmp_path: Path,
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
    read_lines: Callable[[Path], list[str]],
    read_history: Callable[[], list[dict[str, Any]]],
) -> None:
    """MCP のツールの結果の全文の文書だけを記録する（正常系）。"""
    # 準備
    rule_a = rule_file("a.md", "test")
    rule_b = rule_file("b.md", "test")
    index = make_index(
        "rules:\n"
        f"  - rule: {rule_a}\n"
        '    paths:\n      - "**/*.py"\n'
        f"  - rule: {rule_b}\n"
        '    paths:\n      - "**/*.py"\n'
    )
    env = settings_env(indexes=[str(index)])
    payload = hook_payload(
        "PostToolUse",
        tool_name="mcp__docs__get_doc",
        tool_input={"id": "a"},
        cwd=tmp_path,
        tool_response=(
            '<document path="rules/a.md" scope="full">本文 A</document>\n'
            '<document path="rules/b.md" scope="summary">説明 B</document>'
        ),
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert read_lines(state_dir / f"{session_id}.txt") == [f"{rule_a}\t{HASH_TEST}"]
    history = read_history()
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["location"] == str(rule_a)


def test_record_read_when_mcp_document_without_read_by(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
) -> None:
    """書式に従う文書がある結果には `read_by` を当てない（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    index = make_index(index_text(str(rule), read_by=[{"tools": ["mcp__docs__get_doc"]}]))
    env = settings_env(indexes=[str(index)])
    payload = hook_payload(
        "PostToolUse",
        tool_name="mcp__docs__get_doc",
        tool_input={"id": "a"},
        tool_response={"path": "other.md", "scope": "full"},
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


def test_record_read_when_mcp_document_is_url(
    rule_env: tuple[dict[str, str], Path],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    session_id: str,
) -> None:
    """`path` が URL の文書は記録しない（正常系）。"""
    # 準備
    env, _ = rule_env
    payload = hook_payload(
        "PostToolUse",
        tool_name="mcp__docs__get_doc",
        tool_input={"id": "a"},
        tool_response={"path": "https://example.com/a.md", "scope": "full"},
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()


def test_record_read_when_rule_unreadable(
    tmp_path: Path,
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    state_dir: Path,
    log_folder: Path,
    session_id: str,
) -> None:
    """ハッシュを取れないルールは記録しない（正常系）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    index = make_index(index_text(str(missing), read_by=[{"tools": ["mcp__docs__get_doc"]}]))
    env = settings_env(indexes=[str(index)])
    payload = hook_payload("PostToolUse", tool_name="mcp__docs__get_doc", tool_input={"id": "a"})
    # 実行
    result = record_read(payload, env)
    # 検証
    assert result is None
    assert not (state_dir / f"{session_id}.txt").exists()
    assert not (state_dir / f"{session_id}.history.jsonl").exists()
    assert not log_folder.exists()


def test_record_read_when_settings_unreadable(
    xdg_state_home: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    default_log_folder: Path,
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めないときは記録せずに知らせる（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    env = unreadable_env("missing")
    payload = hook_payload(
        "PostToolUse",
        tool_name="Read",
        tool_input={"file_path": str(rule)},
        tool_response=_read_response(1, 3, 3),
    )
    # 実行
    result = record_read(payload, env)
    # 検証
    context = result["hookSpecificOutput"]["additionalContext"]
    assert SETTINGS_FAILURE_SUMMARY in context
    assert env["RULE_INJECT_CONFIG"] in context
    assert str(default_log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
    state_folder = xdg_state_home / "rule-inject"
    assert not (state_folder / f"{session_id}.txt").exists()
    assert not (state_folder / f"{session_id}.history.jsonl").exists()
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
