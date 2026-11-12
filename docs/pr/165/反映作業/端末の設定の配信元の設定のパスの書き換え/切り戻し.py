"""実行で退避した端末の設定へ戻し、dev-docs に読み直させる（作業 PR を develop から revert した後に使う）。"""

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.config/dev-docs/settings.yaml")
BACKUP = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.bak-pr165")
CLONE = "/mnt/c/Users/shuhe/repo/rule-inject"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# 実行.py の RELOAD_TIMEOUT と同じ値
RELOAD_TIMEOUT = 500


def main() -> int:
    """退避したファイルを書き戻して読み直させる。"""
    if not BACKUP.is_file():
        print("退避したファイル: failed")
        print(f"{BACKUP} がありません", file=sys.stderr)
        return 1
    shown = subprocess.run(
        ["git", "-C", CLONE, "cat-file", "-e", "develop:dev-docs.yaml"],
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode != 0:
        print("戻す先の設定: failed")
        print(
            f"git -C {CLONE} cat-file -e develop:dev-docs.yaml: {shown.stderr.strip()}"
            "（作業 PR を develop から revert していないため、戻すと配信が止まる）",
            file=sys.stderr,
        )
        return 1
    print("戻す先の設定: ok")
    shutil.copy2(BACKUP, SETTINGS)
    print("設定の書き戻し: changed")
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "reload", "arguments": {"format": "markdown"}},
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
        with urllib.request.urlopen(request, timeout=RELOAD_TIMEOUT) as response:
            result = json.load(response)
    except OSError as error:
        print("配信元の読み直し: failed")
        print(f"POST {ADMIN_MCP_URL} reload: {error}", file=sys.stderr)
        return 1
    if "error" in result or result.get("result", {}).get("isError"):
        print("配信元の読み直し: failed")
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        return 1
    print("配信元の読み直し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
