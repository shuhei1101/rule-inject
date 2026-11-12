"""端末の設定の配信元 rule-inject の config を project-index.yaml へ書き換え、dev-docs に読み直させる。"""

import difflib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

SETTINGS = Path("/home/shuhei2441/.config/dev-docs/settings.yaml")
BACKUP = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.bak-pr165")
COUNT_FILE = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.count-pr165")
TEMPORARY = Path("/home/shuhei2441/.config/dev-docs/settings.yaml.tmp-pr165")
OLD_LINE = "  - config: /mnt/c/Users/shuhe/repo/rule-inject/dev-docs.yaml\n"
NEW_LINE = "  - config: /mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml\n"
NEW_CONFIG = "/mnt/c/Users/shuhe/repo/rule-inject/project-index.yaml"
CLONE = "/mnt/c/Users/shuhe/repo/rule-inject"
DEVELOP_WORKTREE = "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop"
SOURCES_URL = "http://127.0.0.1:8781/_api/settings/sources"
DOCS_MCP_URL = "http://127.0.0.1:8781/mcp/"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# dev-docs のログで観測した reload の所要時間の最大 332 秒（2026-11-12 17:27〜17:33）+ その 50% を切り上げた値
RELOAD_TIMEOUT = 500
# 読み取りの問い合わせは、読み込み中の配信元を待つことがあるため reload と同じ上限にする
READ_TIMEOUT = 500


def fail(step: str, detail: str) -> int:
    """failed の行と、失敗した手順の stderr を出す。"""
    print(f"{step}: failed")
    print(detail, file=sys.stderr)
    return 1


def call_tool(url: str, name: str, arguments: dict[str, Any], timeout: int) -> str:
    """dev-docs の MCP のツールを tools/call で呼び、結果の本文を返す。"""
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if "error" in result or result.get("result", {}).get("isError"):
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return "\n".join(item.get("text", "") for item in result["result"]["content"])


def rule_inject_row() -> dict[str, Any] | None:
    """dev-docs が今読んでいる端末の設定の rule-inject の行を返す。"""
    with urllib.request.urlopen(SOURCES_URL, timeout=READ_TIMEOUT) as response:
        view = json.load(response)
    rows = [row for row in view["sources"] if row["id"] == "rule-inject"]
    return rows[0] if len(rows) == 1 else None


def count_documents() -> str:
    """develop の worktree を作業場所にした rule-inject の文書の件数の行を返す。"""
    arguments = {"source": "rule-inject", "view": "count", "cwd": DEVELOP_WORKTREE}
    return call_tool(DOCS_MCP_URL, "search_docs", arguments, READ_TIMEOUT).strip()


def record_count() -> None:
    """適用前の件数を、まだ記録していなければ記録する。"""
    if COUNT_FILE.is_file():
        print(f"適用前の件数: {COUNT_FILE.read_text(encoding='utf-8').strip()}")
        return
    try:
        count = count_documents()
    except (OSError, RuntimeError, KeyError) as error:
        print("適用前の件数: missing")
        print(f"search_docs: {error}", file=sys.stderr)
        return
    COUNT_FILE.write_text(count + "\n", encoding="utf-8")
    print(f"適用前の件数: {count}")


def reload_if_needed(dry_run: bool) -> int:
    """dev-docs が新しい config で配信していなければ reload する。"""
    try:
        row = rule_inject_row()
    except OSError as error:
        return fail("配信元の読み直し", f"GET {SOURCES_URL}: {error}")
    if row is not None and row["config"] == [NEW_CONFIG] and row["status"] == "serving":
        print("配信元の読み直し: skipped")
        return 0
    if dry_run:
        print("配信元の読み直し: changed")
        return 0
    try:
        print(call_tool(ADMIN_MCP_URL, "reload", {"format": "markdown"}, RELOAD_TIMEOUT))
    except (OSError, RuntimeError, KeyError) as error:
        return fail("配信元の読み直し", f"POST {ADMIN_MCP_URL} reload: {error}")
    print("配信元の読み直し: changed")
    return 0


def main(args: list[str]) -> int:
    """前提確認 → 計画 → 適用の順に進める。"""
    # 前提確認
    if len(args) > 1 or (len(args) == 1 and args[0] != "--dry-run"):
        return fail("前提確認", f"受け付けない引数: {args}")
    dry_run = args == ["--dry-run"]
    if not SETTINGS.is_file():
        return fail("前提確認", f"{SETTINGS} がありません")
    shown = subprocess.run(
        ["git", "-C", CLONE, "cat-file", "-e", "develop:project-index.yaml"],
        capture_output=True,
        text=True,
        check=False,
    )
    if shown.returncode != 0:
        return fail(
            "前提確認",
            f"git -C {CLONE} cat-file -e develop:project-index.yaml: {shown.stderr.strip()}"
            "（作業 PR が develop へ入っていないか、クローンの develop が古い）",
        )
    before = SETTINGS.read_text(encoding="utf-8")
    lines = before.splitlines(keepends=True)
    done = lines.count(NEW_LINE) == 1 and lines.count(OLD_LINE) == 0
    if not done and lines.count(OLD_LINE) != 1:
        return fail("前提確認", f"{SETTINGS} に {OLD_LINE.strip()} の行が 1 つではありません")
    print("前提確認: ok")
    if dry_run:
        print(f"適用前の件数: {count_documents()}")
    else:
        record_count()

    # 計画（--dry-run もここを通る）
    if done:
        print("設定の書き換え: skipped")
        return reload_if_needed(dry_run)
    after = "".join(NEW_LINE if line == OLD_LINE else line for line in lines)
    sys.stdout.writelines(
        difflib.unified_diff(lines, after.splitlines(keepends=True), str(SETTINGS), str(SETTINGS))
    )
    if dry_run:
        print("設定の書き換え: changed")
        return reload_if_needed(dry_run)

    # 適用（一時ファイル → 検証 → 退避 → 置き換え → 読み直し）
    TEMPORARY.write_text(after, encoding="utf-8")
    written = TEMPORARY.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = [(old, new) for old, new in zip(lines, written, strict=False) if old != new]
    if len(written) != len(lines) or changed != [(OLD_LINE, NEW_LINE)]:
        TEMPORARY.unlink()
        return fail("検証", f"{TEMPORARY} の差分が {OLD_LINE.strip()} の 1 行だけではありません")
    print("検証: ok")
    shutil.copy2(SETTINGS, BACKUP)
    if BACKUP.read_text(encoding="utf-8") != before:
        TEMPORARY.unlink()
        return fail("退避", f"{BACKUP} の中身が {SETTINGS} と一致しません")
    print("退避: ok")
    TEMPORARY.replace(SETTINGS)
    print("設定の書き換え: changed")
    return reload_if_needed(dry_run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
