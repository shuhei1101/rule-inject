"""端末の設定と、配信している dev-docs のサーバー・管理用 MCP・クローンに読み取りだけでつながるかを確かめる。"""

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.config/dev-docs/settings.yaml")
CLONE = "/mnt/c/Users/shuhe/repo/rule-inject"
SOURCES_URL = "http://127.0.0.1:8781/_api/settings/sources"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# 実行.py の READ_TIMEOUT と同じ値
READ_TIMEOUT = 500


def main() -> int:
    """対象ごとに結果の行を出す。"""
    rc = 0
    if SETTINGS.is_file():
        print("端末の設定: ok")
    else:
        print("端末の設定: failed")
        print(f"{SETTINGS} がありません", file=sys.stderr)
        rc = 1
    shown = subprocess.run(
        ["git", "-C", CLONE, "rev-parse", "--verify", "develop"],
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode == 0:
        print("クローンの develop: ok")
    else:
        print("クローンの develop: failed")
        print(f"git -C {CLONE} rev-parse --verify develop: {shown.stderr.strip()}", file=sys.stderr)
        rc = 1
    try:
        with urllib.request.urlopen(SOURCES_URL, timeout=READ_TIMEOUT) as response:
            json.load(response)
        print("dev-docs のサーバー: ok")
    except OSError as error:
        print("dev-docs のサーバー: failed")
        print(f"GET {SOURCES_URL}: {error}", file=sys.stderr)
        rc = 1
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "status", "arguments": {"format": "json"}},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ADMIN_MCP_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=READ_TIMEOUT) as response:
            result = json.load(response)
        if "error" in result or result.get("result", {}).get("isError"):
            raise RuntimeError(json.dumps(result, ensure_ascii=False))
        print("dev-docs の管理用 MCP: ok")
    except (OSError, RuntimeError) as error:
        print("dev-docs の管理用 MCP: failed")
        print(f"POST {ADMIN_MCP_URL} status: {error}", file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
