"""hooks/session_id_injection.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rule_inject.hooks.session_id_injection import inject_session_id

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def test_inject_session_id(
    hook_payload: Callable[..., dict[str, Any]],
    session_id: str,
) -> None:
    """元の引数を写して session_id を足す（正常系）。"""
    # 準備
    tool_input = {"locations": ["/r/a.md"], "paths": ["/p/src/a.py"]}
    payload = hook_payload("PreToolUse", tool_name=READ_RULES_TOOL, tool_input=tool_input)
    # 実行
    result = inject_session_id(payload, {})
    # 検証
    output = result["hookSpecificOutput"]
    assert output["updatedInput"] == {**tool_input, "session_id": session_id}
    assert "permissionDecision" not in output


def test_inject_session_id_when_model_supplied(
    hook_payload: Callable[..., dict[str, Any]],
    session_id: str,
) -> None:
    """モデルが渡した session_id を入力の値で上書きする（正常系）。"""
    # 準備
    tool_input = {"locations": ["/r/a.md"], "session_id": "model-supplied"}
    payload = hook_payload("PreToolUse", tool_name=READ_RULES_TOOL, tool_input=tool_input)
    # 実行
    result = inject_session_id(payload, {})
    # 検証
    assert result["hookSpecificOutput"]["updatedInput"]["session_id"] == session_id
