"""切り戻し: 依頼先のリポジトリの、開いている依頼の Issue を not planned で閉じる。"""

from __future__ import annotations

import sys

from _common import TARGET_REPOS, find_issue, run_gh

OPEN_STATE = "OPEN"


def main() -> int:
    """閉じた結果の行を出し、failed があれば 1 を返す。"""
    failed = False
    for repo in TARGET_REPOS:
        try:
            issue = find_issue(repo)
        except RuntimeError as exc:
            print(f"{repo} の依頼の Issue のクローズ: failed（{exc}）")
            failed = True
            continue
        # 無いか、既に閉じていれば何もしない
        if issue is None or issue.state != OPEN_STATE:
            print(f"{repo} の依頼の Issue のクローズ: skipped")
            continue
        result = run_gh(
            ["issue", "close", str(issue.number), "--repo", repo, "--reason", "not planned"]
        )
        if result.returncode != 0:
            print(f"{repo} の依頼の Issue のクローズ: failed（{result.stderr.strip()}）")
            failed = True
            continue
        print(f"{repo} の依頼の Issue のクローズ: changed（#{issue.number}）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
