"""実行: 依頼先のリポジトリごとに、索引の参照するツールの記載を依頼する Issue を起票する（`--dry-run` は計画まで）。"""

from __future__ import annotations

import sys

from _common import ISSUE_BODY, ISSUE_TITLE, TARGET_REPOS, find_issue, run_gh

DRY_RUN_FLAG = "--dry-run"


def main(argv: list[str]) -> int:
    """前提確認 → 計画 → 適用の順に進め、failed があれば 1 を返す。"""
    dry_run = DRY_RUN_FLAG in argv
    # 前提確認: gh がログイン済みで、依頼先が 1 件以上ある
    if run_gh(["auth", "status"]).returncode != 0 or not TARGET_REPOS:
        print("前提確認: failed")
        return 1
    print("前提確認: ok")

    # 計画: 依頼の Issue がまだ無いリポジトリを選ぶ（--dry-run もここを通る）
    planned: list[str] = []
    for repo in TARGET_REPOS:
        try:
            existing = find_issue(repo)
        except RuntimeError as exc:
            print(f"{repo} の Issue の起票: failed（{exc}）")
            return 1
        if existing is not None:
            print(f"{repo} の Issue の起票: skipped（#{existing.number} {existing.state}）")
            continue
        planned.append(repo)
        print(f"起票する: {repo}「{ISSUE_TITLE}」")
    if dry_run:
        for repo in planned:
            print(f"{repo} の Issue の起票: changed")
        return 0

    # 適用: 冪等でないため再試行せず、失敗したら止める
    for repo in planned:
        result = run_gh(
            ["issue", "create", "--repo", repo, "--title", ISSUE_TITLE, "--body-file", "-"],
            stdin=ISSUE_BODY,
        )
        if result.returncode != 0:
            print(f"{repo} の Issue の起票: failed（{result.stderr.strip()}）")
            return 1
        print(f"{repo} の Issue の起票: changed（{result.stdout.strip()}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
