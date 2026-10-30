"""develop の worktree の配信元が、違反もずれも無く配信されているかを読むだけで確かめる。"""

import json
import sys
import urllib.request

DEVELOP_WORKTREE = "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# check_project・status は索引の同期を数え直すため、数分かかることがある
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
    """check_project と status の観測した値を 1 行ずつ出す。"""
    failed = False
    project = call_admin_tool("check_project", {"path": DEVELOP_WORKTREE, "format": "json"})

    # 設定のバージョンが dev-docs の今のバージョンか
    print(f"設定のバージョン: {project['config_version']}（{project['version_state']}）")
    if project["version_state"] != "current":
        failed = True

    # 違反があるか（check_project は違反が 0 件のとき violations を返さない）
    violations = project.get("violations", [])
    print(f"違反: {len(violations)} 件")
    if violations:
        failed = True

    # 索引の同期のずれがあるか（違反があると sync を返さない）
    if "sync" in project:
        drift = sum(project["sync"].values())
        print(f"索引の同期のずれ: {drift} 件")
        if drift:
            failed = True

    # 端末の設定に登録された配信元が配信中か
    source_id = project.get("registered_id")
    if source_id is None:
        print("配信の状態: failed（端末の設定に登録されていない）")
        return 1
    status = call_admin_tool("status", {"format": "json"})
    state = next((source["status"] for source in status["sources"] if source["id"] == source_id), None)
    print(f"配信の状態: {source_id} は {state}")
    if state != "serving":
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
