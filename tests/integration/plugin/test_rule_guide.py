"""ルール案内（PreToolUse フック）の結合テスト。"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

RULE = "/r/python.md"
OWN_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


@pytest.fixture
def write_index(
    make_index: Callable[..., Path], index_text: Callable[..., str]
) -> Callable[..., Path]:
    """エントリを並べた索引を書き、そのパスを返す factory。"""

    def _write(*entries: dict[str, Any]) -> Path:
        """entries を索引の YAML にして書く。"""
        return make_index(index_text(*entries))

    return _write


@pytest.fixture
def write_payload(
    tmp_path: Path, hook_payload: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """まだ無い .py のパスを Write する PreToolUse の入力を作る factory。"""

    def _make(relative: str = "src/app.py") -> dict[str, Any]:
        """tmp_path の下の relative を書く Write の入力を返す。"""
        return hook_payload(
            "PreToolUse",
            tool_name="Write",
            tool_input={"file_path": str(tmp_path / relative), "content": ""},
        )

    return _make


def test_normal_when_blocked(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """書く操作が必須の未読のルールで Write を止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert "read_rules" in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_normal_when_already_read(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
) -> None:
    """当たるルールが既読なら何も出さない（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    write_record([RULE])
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_not_blocked(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """操作の種別が `on` に当たらない未読のルールは止めずに案内する（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]
    assert "やり直してください" not in output["additionalContext"]
    assert completed.returncode == 0


def test_normal_when_read_by_bash(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """読むコマンドの引数から取り出したパスで照合して止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["read"]})
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print()\n", encoding="utf-8")
    payload = hook_payload(
        "PreToolUse",
        tool_name="Bash",
        tool_input={"command": "cd src && cat app.py | head -n 5"},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


def test_normal_when_mcp_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """`tools` の glob に当たる MCP のツールの呼び出しを止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "tools": ["mcp__*__create_*"]})
    payload = hook_payload("PreToolUse", tool_name="mcp__github__create_issue", tool_input={})
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


def test_normal_when_duplicate_entries(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """同じルールのエントリ 2 つを 1 件にまとめ、どちらかが止めるなら止める（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = make_index(
        index_text(
            {"rule": str(rule), "paths": ["**/*.py"], "on": ["read"]},
            {"rule": "./rules/python.md", "paths": ["**/*.py"], "on": ["write"]},
        )
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"].count(str(rule)) == 1


def test_normal_when_excluded(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`exclude` に当たるパスには案内しない（正常系）。"""
    # 準備
    index = write_index(
        {"rule": RULE, "paths": ["**/*.py"], "exclude": ["**/tests/**"], "on": ["write"]}
    )
    # 実行
    completed = run_hook("rule_guide", write_payload("tests/test_app.py"), index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


@pytest.fixture
def hundred_entries() -> list[dict[str, Any]]:
    """1 件 150 字前後の場所を持つ 100 件のエントリ（半数は書く操作が必須、半数は読む操作が必須）。"""
    return [
        {
            "rule": f"/rules/{'write' if number % 2 == 0 else 'read'}/{number:03d}/" + "x" * 130,
            "paths": ["**/*.py"],
            "on": ["write"] if number % 2 == 0 else ["read"],
        }
        for number in range(100)
    ]


def test_normal_when_guidance_too_long(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    hundred_entries: list[dict[str, Any]],
) -> None:
    """案内が 10,000 字を超えるとき、収まる分だけ載せて残りの件数を添える（正常系）。"""
    # 準備
    index = write_index(*hundred_entries)
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    reason = json.loads(completed.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert len(reason) <= 10000
    assert reason.index("/rules/write/") < reason.index("/rules/read/")
    assert re.search(r"ほか \d+ 件のルール", reason)


def test_normal_when_own_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """このプラグインの MCP のツールには、当たるエントリがあっても案内しない（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "tools": ["mcp__*"]})
    payload = hook_payload(
        "PreToolUse", tool_name=OWN_TOOL, tool_input={"locations": [RULE], "session_id": "s"}
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_error_when_index_unreadable(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """索引が無いか書式に合わないとき、操作を止めずに理由を載せる（異常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    broken = make_index("rules:\n  - foo: bar\n", "broken.yaml")
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=f"{missing},{broken}")
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(missing) in output["additionalContext"]
    assert str(broken) in output["additionalContext"]
    assert completed.returncode == 0


def test_error_when_record_unreadable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    unwritable: Callable[[Path, int], Path],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """記録ファイルが読めないとき、操作を止めずに理由を載せ、ログに書く（異常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    record_file = unwritable(write_record([RULE]), 0o000)
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(record_file) in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_record"
    assert completed.returncode == 0


def test_normal_when_read_by_grep(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """組み込みの Grep が指すファイルで照合して止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["read"]})
    target = tmp_path / "app.py"
    target.write_text("print()\n", encoding="utf-8")
    payload = hook_payload(
        "PreToolUse", tool_name="Grep", tool_input={"pattern": "print", "path": str(target)}
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
