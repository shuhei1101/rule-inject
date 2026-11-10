"""確認: 依頼先の全てのリポジトリに、依頼の Issue があるかを読むだけで確かめる。"""

from __future__ import annotations

import sys

from _common import TARGET_REPOS, find_issue, has_index


def main() -> int:
    """観測した Issue の番号と状態を出し、無いリポジトリがあれば 1 を返す。"""
    failed = False
    for repo in TARGET_REPOS:
        try:
            index = has_index(repo)
            issue = find_issue(repo) if index is not None else None
        except RuntimeError as exc:
            print(f"{repo} の依頼の Issue: failed（{exc}）")
            failed = True
            continue
        # 索引が無いリポジトリは依頼の対象外
        if index is None:
            print(f"{repo} の依頼の Issue: skipped（索引が無い）")
            continue
        # 依頼の Issue が無ければ、まだ効いていない
        if issue is None:
            print(f"{repo} の依頼の Issue: failed（無い）")
            failed = True
            continue
        print(f"{repo} の依頼の Issue: ok（#{issue.number} {issue.state}）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
