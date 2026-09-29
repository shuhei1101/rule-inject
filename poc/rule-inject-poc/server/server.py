"""受け取った引数をそのまま返す PoC の MCP サーバー。"""
import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

LOG = Path(__file__).resolve().parents[1] / "poc.log.jsonl"
mcp = MCPServer("poc")


@mcp.tool()
def echo(location: str, session_id: str | None = None) -> str:
    """受け取った location と session_id を返す。

    Args:
        location: ルールの場所
        session_id: セッションの識別子（フックが足すので渡さない）
    """
    record = {
        "from": "tool",
        "run": os.environ.get("POC_RUN"),
        "location": location,
        "session_id": session_id,
        "env_session_id": os.environ.get("CLAUDE_CODE_SESSION_ID"),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return json.dumps(record, ensure_ascii=False)


mcp.run()
