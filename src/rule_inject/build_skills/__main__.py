"""SKILL.md の生成の入口（`python -m rule_inject.build_skills`）。"""

from __future__ import annotations

import sys
from pathlib import Path

from rule_inject.features.build_skills.service import build_skills
from rule_inject.features.build_skills.types import SkillBuildError

# どのファイルも書き換えなかったときの終了コード
FAILURE_EXIT_CODE = 2


def main() -> None:
    """作業ディレクトリをリポジトリの直下として SKILL.md を生成し、書き換えたパスを書き込む。"""
    try:
        written = build_skills(Path.cwd())
    except SkillBuildError as exc:
        for problem in exc.problems:
            print(problem, file=sys.stderr)
        sys.exit(FAILURE_EXIT_CODE)
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
