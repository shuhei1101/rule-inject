"""疎通確認: gh の認証と、依頼先の全てのリポジトリの Issue を読めるかを確かめる（状態は変えない）。"""

from __future__ import annotations

import sys

from _common import TARGET_REPOS, find_issue, has_index, run_gh


def main() -> int:
    """結果の行を出し、failed があれば 1 を返す。"""
    failed = False
    # gh がログイン済みか
    if run_gh(["auth", "status"]).returncode == 0:
        print("gh の認証: ok")
    else:
        print("gh の認証: failed")
        return 1
    # 依頼先ごとに、Issue の一覧を読めるか
    for repo in TARGET_REPOS:
        try:
            has_index(repo)
            find_issue(repo)
        except RuntimeError as exc:
            print(f"{repo} の索引と Issue の読み取り: failed（{exc}）")
            failed = True
            continue
        print(f"{repo} の索引と Issue の読み取り: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
