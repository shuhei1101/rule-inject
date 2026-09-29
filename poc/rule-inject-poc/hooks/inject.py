"""MCP ツールの引数へ session_id を足す PoC のフック。"""
import json
import os
import sys
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "poc.log.jsonl"


def main() -> None:
    """フックの入力を記録し、POC_MODE に応じた updatedInput を返す。"""
    data = json.load(sys.stdin)
    mode = os.environ.get("POC_MODE", "none")
    updated = {**data.get("tool_input", {}), "session_id": data["session_id"]}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "from": "hook",
            "run": os.environ.get("POC_RUN"),
            "mode": mode,
            "session_id": data["session_id"],
            "tool_name": data.get("tool_name"),
            "tool_input": data.get("tool_input"),
        }, ensure_ascii=False) + "\n")
    output = {"hookEventName": "PreToolUse", "updatedInput": updated}
    # none のときは permissionDecision を付けない
    if mode in ("allow", "ask"):
        output["permissionDecision"] = mode
        output["permissionDecisionReason"] = f"PoC: {mode}"
    print(json.dumps({"hookSpecificOutput": output}))


main()
