"""develop の worktree へ origin/develop を取り込み、dev-docs に配信元の設定を読み直させる。"""

import json
import subprocess
import sys
import urllib.request

DEVELOP_WORKTREE = "/mnt/c/Users/shuhe/repo/rule-inject/.claude/worktrees/develop"
ADMIN_MCP_URL = "http://127.0.0.1:8781/_admin/mcp/"
# reload は全ての配信元を検証し直すため、数分かかることがある
ADMIN_MCP_TIMEOUT_SEC = 300
# この作業で develop の worktree へ効かせるファイル
TARGET_FILES = [
    "dev-docs.yaml",
    "schemas/files.schema.yaml",
    "docs/files.yaml",
    "src/files.yaml",
    "hooks/files.yaml",
    "tests/files.yaml",
]
# 作業 PR #79 で入る設定のバージョンの行
EXPECTED_CONFIG_VERSION = 'version: "3"'


def git(*args: str) -> subprocess.CompletedProcess:
    """develop の worktree で git を 1 回実行する。"""
    return subprocess.run(["git", "-C", DEVELOP_WORKTREE, *args], capture_output=True, text=True)


def call_admin_tool(name: str, arguments: dict) -> dict:
    """管理の MCP のツールを 1 回呼び、structuredContent を返す。"""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    request = urllib.request.Request(ADMIN_MCP_URL, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=ADMIN_MCP_TIMEOUT_SEC) as response:
        result = json.loads(response.read().decode())["result"]
    return result["structuredContent"]


def main() -> int:
    """前提確認 → 計画 → 適用の順に、手順ごとの結果を 1 行ずつ出す。"""
    dry_run = len(sys.argv) > 1 and sys.argv[1] == "--dry-run"

    # 前提確認: develop を踏んでいて、追跡しているファイルに手元の変更が無いか
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    if branch.stdout.strip() != "develop" or dirty.stdout.strip():
        print("前提確認: failed（develop の worktree が develop でないか、手元の変更がある）")
        return 1
    if git("fetch", "origin", "develop").returncode != 0:
        print("前提確認: failed（origin/develop を取得できない）")
        return 1
    # マージ済みか: origin/develop の dev-docs.yaml が設定のバージョン 3 で、files.yaml を持つか
    remote_config = git("show", "origin/develop:dev-docs.yaml")
    has_files = git("cat-file", "-e", "origin/develop:src/files.yaml").returncode == 0
    if EXPECTED_CONFIG_VERSION not in remote_config.stdout or not has_files:
        print("前提確認: failed（origin/develop に作業 PR #79 の変更が入っていない）")
        return 1
    print("前提確認: ok")

    # 計画: 取り込みが要るか（--dry-run もここまで通る）
    head = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", "origin/develop").stdout.strip()
    needs_merge = head != remote
    if needs_merge:
        # 早送りできない（develop の worktree に push していない commit がある）なら止める
        if git("merge-base", "--is-ancestor", "HEAD", "origin/develop").returncode != 0:
            print("develop の取り込み: failed（早送りできない）")
            return 1
        print(git("diff", "--stat", "HEAD", "origin/develop", "--", *TARGET_FILES).stdout, end="")
    if dry_run:
        # 適用せず、適用したときの結果だけを出す
        print(f"develop の取り込み: {'changed' if needs_merge else 'skipped'}")
        print("配信元の読み直し: changed")
        return 0

    # 適用: 早送りで取り込み、dev-docs に読み直させる
    if not needs_merge:
        print("develop の取り込み: skipped")
    elif git("merge", "--ff-only", "origin/develop").returncode == 0:
        print("develop の取り込み: changed")
    else:
        print("develop の取り込み: failed")
        return 1
    try:
        call_admin_tool("reload", {"format": "json"})
    except OSError as error:
        print(f"配信元の読み直し: failed（{error}）")
        return 1
    print("配信元の読み直し: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
