"""develop の worktree と dev-docs の管理の MCP へ、読み取りだけでつながるかを確かめる。"""

import json
import subprocess
import sys
import urllib.request

DEVELOP_WORKTREE = "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# status は全ての配信元の索引の同期を数え直すため、数分かかることがある
ADMIN_MCP_TIMEOUT_SEC = 300


def call_admin_tool(name: str, arguments: dict) -> dict:
    """管理の MCP のツールを 1 回呼び、structuredContent を返す。"""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    request = urllib.request.Request(ADMIN_MCP_URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=ADMIN_MCP_TIMEOUT_SEC) as response:
        result = json.loads(response.read().decode())["result"]
    return result["structuredContent"]


def main() -> int:
    """develop の worktree と管理の MCP の疎通を 1 行ずつ出す。"""
    failed = False

    # develop の worktree が develop を踏んだ Git の作業ツリーか
    branch = subprocess.run(
        ["git", "-C", DEVELOP_WORKTREE, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if branch.returncode == 0 and branch.stdout.strip() == "develop":
        print("develop の worktree: ok")
    else:
        print("develop の worktree: failed")
        failed = True

    # 管理の MCP が応答し、status を返すか
    try:
        status = call_admin_tool("status", {"format": "json"})
        print(f"dev-docs の管理の MCP: ok（配信元 {len(status['sources'])} 件）")
    except OSError as error:
        print(f"dev-docs の管理の MCP: failed（{error}）")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
