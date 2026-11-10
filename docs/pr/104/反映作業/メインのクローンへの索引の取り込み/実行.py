"""実行: メインのクローンに直下の rules.yaml が無ければ、origin/master を fast-forward で取り込む。

--dry-run を付けると、取り込む commit と変わるファイルの一覧を出して止まる。
"""

from __future__ import annotations

import sys

from _common import BRANCH, INDEX, REMOTE_BRANCH, run_git


def main(dry_run: bool) -> int:
    """結果の行を出し、failed があれば 1 を返す。"""
    # 前提確認: master を踏んでいて、追跡しているファイルに未 commit の変更が無い
    head = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if head.returncode != 0 or head.stdout.strip() != BRANCH:
        print(f"前提確認: failed（ブランチ: {head.stdout.strip() or head.stderr.strip()}）")
        return 1
    status = run_git(["status", "--porcelain", "--untracked-files=no"])
    if status.returncode != 0 or status.stdout.strip():
        detail = status.stdout.strip() or status.stderr.strip()
        print(f"前提確認: failed（未 commit の変更: {detail}）")
        return 1
    print("前提確認: ok")

    # 計画（--dry-run もここを通る）
    # 既に索引があれば何もしない
    if INDEX.is_file():
        print("索引の取り込み: skipped")
        return 0
    fetch = run_git(["fetch", "origin", BRANCH])
    if fetch.returncode != 0:
        print(f"origin の取得: failed（{fetch.stderr.strip()}）")
        return 1
    # origin/master に索引が入っていなければ、取り込んでも効かない
    if run_git(["cat-file", "-e", f"{REMOTE_BRANCH}:rules.yaml"]).returncode != 0:
        print(f"{REMOTE_BRANCH} の rules.yaml: failed（まだ入っていない）")
        return 1
    print(f"{REMOTE_BRANCH} の rules.yaml: ok")
    # HEAD が origin/master の祖先でなければ、fast-forward で取り込めない
    if run_git(["merge-base", "--is-ancestor", "HEAD", REMOTE_BRANCH]).returncode != 0:
        print("fast-forward の可否: failed（HEAD が origin/master の祖先でない）")
        return 1
    print("fast-forward の可否: ok")
    print(run_git(["log", "--oneline", f"HEAD..{REMOTE_BRANCH}"]).stdout.rstrip())
    print(run_git(["diff", "--stat", f"HEAD..{REMOTE_BRANCH}"]).stdout.rstrip())
    if dry_run:
        print("索引の取り込み: changed")
        return 0

    # 適用: fast-forward だけで取り込む
    merge = run_git(["merge", "--ff-only", REMOTE_BRANCH])
    if merge.returncode != 0 or not INDEX.is_file():
        print(f"索引の取り込み: failed（{merge.stderr.strip()}）")
        return 1
    print("索引の取り込み: changed")
    return 0


if __name__ == "__main__":
    sys.exit(main("--dry-run" in sys.argv[1:]))
