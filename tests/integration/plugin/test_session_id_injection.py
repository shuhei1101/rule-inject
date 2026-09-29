"""セッションIDの付与（PreToolUse フック）の結合テスト。"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    session_id: str,
) -> None:
    """元の引数に session_id を足した updatedInput を返す（正常系）。"""
    # 準備
    tool_input = {"locations": ["/r/a.md"], "paths": ["/p/src/a.py"]}
    payload = hook_payload("PreToolUse", tool_name=READ_RULES_TOOL, tool_input=tool_input)
    # 実行
    completed = run_hook("session_id_injection", payload)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert completed.returncode == 0
    assert output["updatedInput"]["locations"] == ["/r/a.md"]
    assert output["updatedInput"]["paths"] == ["/p/src/a.py"]
    assert output["updatedInput"]["session_id"] == session_id
    assert "permissionDecision" not in output


def test_normal_when_model_supplied_session_id(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    session_id: str,
) -> None:
    """モデルが渡した session_id をフックの入力の値で上書きする（正常系）。"""
    # 準備
    tool_input = {"locations": ["/r/a.md"], "session_id": "model-supplied"}
    payload = hook_payload("PreToolUse", tool_name=READ_RULES_TOOL, tool_input=tool_input)
    # 実行
    completed = run_hook("session_id_injection", payload)
    # 検証
    updated = json.loads(completed.stdout)["hookSpecificOutput"]["updatedInput"]
    assert updated["session_id"] == session_id
    assert updated["session_id"] != "model-supplied"
