"""配信元 rule-inject の config が project-index.yaml を指して配信され、件数が適用前と同じかを読むだけで確かめる。"""

import json
import sys
import urllib.request
from pathlib import Path

COUNT_FILE = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.count-pr165")
NEW_CONFIG = "/mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml"
DEVELOP_WORKTREE = "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop"
SOURCES_URL = "http://127.0.0.1:8781/_api/settings/sources"
DOCS_MCP_URL = "http://127.0.0.1:8781/mcp/"
# 実行.py の READ_TIMEOUT と同じ値
READ_TIMEOUT = 500


def count_documents() -> str:
    """develop の worktree を作業場所にした rule-inject の文書の件数の行を返す。"""
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_docs",
                "arguments": {"source": "rule-inject", "view": "count", "cwd": DEVELOP_WORKTREE},
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        DOCS_MCP_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as response:
        result = json.load(response)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return "\n".join(item.get("text", "") for item in result["result"]["content"]).strip()


def main() -> int:
    """観測した値を出し、効いていれば 0 で終える。"""
    try:
        with urllib.request.urlopen(SOURCES_URL, timeout=READ_TIMEOUT) as response:
            view = json.load(response)
    except OSError as error:
        print("配信元 rule-inject: failed")
        print(f"GET {SOURCES_URL}: {error}", file=sys.stderr)
        return 1
    rows = [row for row in view["sources"] if row["id"] == "rule-inject"]
    if len(rows) != 1:
        print("配信元 rule-inject: failed")
        print(f"rule-inject の行が {len(rows)} 件あります", file=sys.stderr)
        return 1
    row = rows[0]
    print(f"config: {row['config']}")
    print(f"status: {row['status']}")
    rc = 0
    if row["config"] == [NEW_CONFIG] and row["status"] == "serving":
        print("配信元 rule-inject: ok")
    else:
        print("配信元 rule-inject: failed")
        rc = 1
    if not COUNT_FILE.is_file():
        print("文書の件数: failed")
        print(
            f"{COUNT_FILE} がありません（実行.py が適用前の件数を記録していない）", file=sys.stderr
        )
        return 1
    expected = COUNT_FILE.read_text(encoding="utf-8").strip()
    try:
        actual = count_documents()
    except (OSError, RuntimeError, KeyError) as error:
        print("文書の件数: failed")
        print(f"search_docs: {error}", file=sys.stderr)
        return 1
    print(f"適用前の件数: {expected}")
    print(f"今の件数: {actual}")
    if actual == expected:
        print("文書の件数: ok")
    else:
        print("文書の件数: failed")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
