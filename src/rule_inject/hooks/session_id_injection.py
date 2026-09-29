"""セッションIDの付与（PreToolUse）。MCP のツールの引数へ session_id を足す。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def inject_session_id(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    """tool_input を写して session_id を上書きした updatedInput を返す（許可の判定は返さない）。"""
    # updatedInput は引数を丸ごと置き換えるため、元の引数を落とさずに写す
    updated = {**payload["tool_input"], "session_id": payload["session_id"]}
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}
