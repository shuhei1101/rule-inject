"""疎通確認: メインのクローン・origin・ログのフォルダを読めるかを確かめる（状態は変えない）。"""

from __future__ import annotations

import sys

from _common import BRANCH, LOG_DIR, run_git


def main() -> int:
    """結果の行を出し、failed があれば 1 を返す。"""
    # メインのクローンが git のリポジトリで、master を踏んでいるか
    head = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if head.returncode != 0:
        print(f"メインのクローン: failed（{head.stderr.strip()}）")
        return 1
    if head.stdout.strip() != BRANCH:
        print(f"メインのクローンのブランチ: failed（{head.stdout.strip()}）")
        return 1
    print("メインのクローン: ok")
    # origin の master を読み取りだけで引けるか
    remote = run_git(["ls-remote", "--exit-code", "origin", BRANCH])
    if remote.returncode != 0:
        print(f"origin の master: failed（{remote.stderr.strip()}）")
        return 1
    print("origin の master: ok")
    # ログのフォルダがあるか
    if not LOG_DIR.is_dir():
        print(f"ログのフォルダ: failed（{LOG_DIR} が無い）")
        return 1
    print("ログのフォルダ: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
