"""hooks/rule_guide.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks._runner import SETTINGS_FAILURE_SUMMARY
from rule_inject.hooks.rule_guide import guide_rules

RULE = "/r/python.md"
# 本文が `test` のルールの本文のハッシュ
HASH_TEST = "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


@pytest.fixture
def guide_env(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
) -> Callable[[str], dict[str, str]]:
    """索引の文字列を書き、設定ファイルの `global.indexes` で指す環境変数を返す factory。"""

    def _env(text: str) -> dict[str, str]:
        """text を索引として置き、その索引を指す設定ファイルを `RULE_INJECT_CONFIG` で指す。"""
        return settings_env(indexes=[str(make_index(text))])

    return _env


def test_handle_when_blocked(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """止める（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert "Read で読んでから" in output["permissionDecisionReason"]


def test_handle_when_already_read(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """既読なら何も出さない（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    env = guide_env(index_text(str(rule), paths=["**/*.py"], on=["write"]))
    write_record([f"{rule}\t{HASH_TEST}"])
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    assert result is None


def test_handle_when_not_blocking(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """止めずに案内する（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]


def test_handle_when_bash(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """Bash の読むコマンドで止める（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["read"]))
    target = tmp_path / "app.py"
    target.write_text("print()\n", encoding="utf-8")
    payload = hook_payload("PreToolUse", tool_name="Bash", tool_input={"command": f"cat {target}"})
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


def test_handle_when_grep_folder(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """Grep がフォルダを指すときは照合しない（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*"], on=["read"]))
    payload = hook_payload(
        "PreToolUse",
        tool_name="Grep",
        tool_input={"pattern": "foo", "path": str(tmp_path)},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    assert result is None


def test_handle_when_index_unreadable(
    tmp_path: Path,
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """索引が読めないとき止めずに理由を載せる（正常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    broken = make_index("rules:\n  - foo: bar\n", "broken.yaml")
    env = settings_env(indexes=[str(missing), str(broken)])
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(missing) in output["additionalContext"]
    assert str(broken) in output["additionalContext"]
    assert read_daily_log()[0]["operation"] == "read_index"


def test_handle_when_record_unreadable(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
    unwritable: Callable[[Path, int], Path],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """記録が読めないとき止めずに理由を載せる（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    record_file = unwritable(write_record([f"{RULE}\t{HASH_TEST}"]), 0o000)
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(record_file) in output["additionalContext"]
    assert read_daily_log()[0]["operation"] == "read_record"


def test_handle_when_already_guided(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    write_guided: Callable[[Sequence[str]], Path],
) -> None:
    """案内済みなら止めない案内を出さない（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    write_guided([RULE])
    payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    assert result is None


def test_handle_when_guided_recorded(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """止めない案内に載せた場所だけを案内済みにする（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    guided_file = state_dir / f"{session_id}.guided.txt"
    write_payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    read_payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    blocked = guide_rules(write_payload, env)
    guided_after_write = guided_file.exists()
    guide_rules(read_payload, env)
    # 検証
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not guided_after_write
    assert read_lines(guided_file) == [RULE]


def test_handle_when_guided_unwritable(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    unwritable: Callable[[Path, int], Path],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """案内済みに書けなくても案内を出す（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"], on=["write"]))
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]
    assert str(state_dir / f"{session_id}.guided.txt") in output["additionalContext"]
    assert read_daily_log()[0]["operation"] == "write_record"


def test_handle_when_mcp_args(
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """MCP のツールの引数で当てる（正常系）。"""
    # 準備
    env = guide_env(
        index_text(RULE, tools=["mcp__*__search_*"], args={"kind": ["rule"]}, on=["mcp"]),
    )
    matched = hook_payload(
        "PreToolUse",
        tool_name="mcp__docs__search_docs",
        tool_input={"kind": "rule"},
    )
    unmatched = hook_payload(
        "PreToolUse",
        tool_name="mcp__docs__search_docs",
        tool_input={"kind": "note"},
    )
    # 実行
    blocked = guide_rules(matched, env)
    passed = guide_rules(unmatched, env)
    # 検証
    assert blocked["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert passed is None


def test_handle_when_rule_changed(
    tmp_path: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    write_record: Callable[[Sequence[str]], Path],
) -> None:
    """読んだ後に変わったルールを案内する（正常系）。"""
    # 準備
    rule = rule_file("python.md", "test")
    env = guide_env(index_text(str(rule), paths=["**/*.py"], on=["write"]))
    write_record([f"{rule}\t{HASH_TEST}"])
    rule.write_text("changed", encoding="utf-8")
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert str(rule) in output["permissionDecisionReason"]


def test_handle_when_settings_unreadable(
    tmp_path: Path,
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    default_log_folder: Path,
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めないときは照合せずに知らせる（正常系）。"""
    # 準備
    env = unreadable_env("unknown_key")
    payload = hook_payload(
        "PreToolUse",
        tool_name="Write",
        tool_input={"file_path": str(tmp_path / "src" / "app.py"), "content": ""},
    )
    # 実行
    result = guide_rules(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert "permissionDecision" not in output
    context = output["additionalContext"]
    assert SETTINGS_FAILURE_SUMMARY in context
    assert env["RULE_INJECT_CONFIG"] in context
    assert str(default_log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
