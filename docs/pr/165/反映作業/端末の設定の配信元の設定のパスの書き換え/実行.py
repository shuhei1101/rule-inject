"""端末の設定の配信元 rule-inject の config を project-index.yaml へ書き換え、dev-docs に読み直させる。"""

import difflib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.config/dev-docs/settings.yaml")
BACKUP = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.bak-pr165")
OLD_LINE = "  - config: /mnt/c/Users/shuhe/repo/rule-inject/dev-docs.yaml\n"
NEW_LINE = "  - config: /mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml\n"
NEW_CONFIG = Path("/mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml")
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# 読み直しは全ての配信元を読み込み終えるまで返らないため、待つ上限を長めに取る
RELOAD_TIMEOUT = 300


def fail(step: str, detail: str) -> int:
    """failed の行と、流したコマンドの stderr を出す。"""
    print(f"{step}: failed")
    print(detail, file=sys.stderr)
    return 1


def reload_sources() -> str:
    """dev-docs の管理用 MCP の reload を呼び、結果の本文を返す。"""
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
    with urllib.request.urlopen(request, timeout=RELOAD_TIMEOUT) as response:
        result = json.load(response)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return "\n".join(item.get("text", "") for item in result["result"]["content"])


def main(args: list[str]) -> int:
    """前提確認 → 計画 → 適用の順に進める。"""
    # 前提確認
    if len(args) > 1 or (len(args) == 1 and args[0] != "--dry-run"):
        return fail("前提確認", f"受け付けない引数: {args}")
    dry_run = args == ["--dry-run"]
    if not SETTINGS.is_file():
        return fail("前提確認", f"{SETTINGS} がありません")
    before = SETTINGS.read_text(encoding="utf-8")
    lines = before.splitlines(keepends=True)
    if lines.count(NEW_LINE) == 1 and lines.count(OLD_LINE) == 0:
        print("前提確認: ok")
        print("設定の書き換え: skipped")
        return 0
    if lines.count(OLD_LINE) != 1:
        return fail("前提確認", f"{SETTINGS} に {OLD_LINE.strip()} の行が 1 つではありません")
    if not NEW_CONFIG.is_file():
        return fail("前提確認", f"{NEW_CONFIG} がありません（release が master へ入っていない）")
    print("前提確認: ok")

    # 計画（--dry-run もここを通る）
    after = "".join(NEW_LINE if line == OLD_LINE else line for line in lines)
    sys.stdout.writelines(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(SETTINGS),
            tofile=str(SETTINGS),
        )
    )
    if dry_run:
        print("設定の書き換え: changed")
        print("配信元の読み直し: changed")
        return 0

    # 適用（退避 → 置き換え → 読み直し）
    shutil.copy2(SETTINGS, BACKUP)
    if BACKUP.read_text(encoding="utf-8") != before:
        return fail("退避", f"{BACKUP} の中身が {SETTINGS} と一致しません")
    print("退避: ok")
    temporary = SETTINGS.with_name(SETTINGS.name + ".tmp-pr165")
    temporary.write_text(after, encoding="utf-8")
    temporary.replace(SETTINGS)
    print("設定の書き換え: changed")
    try:
        print(reload_sources())
    except (OSError, RuntimeError, KeyError) as error:
        return fail("配信元の読み直し", f"POST {ADMIN_MCP_URL} reload: {error}")
    print("配信元の読み直し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
