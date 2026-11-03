"""メインのクローンへの索引の取り込みのスクリプトが共有する固定値と git の呼び出し。"""

from __future__ import annotations

import subprocess
from pathlib import Path

# RULE_INJECT_INDEXES_PROJECT が指すメインのクローンと、その直下の索引
MAIN_CLONE = Path("/mnt/c/Users/shuhe/repo/rule-inject")
INDEX = MAIN_CLONE / "rules.yaml"
BRANCH = "master"
REMOTE_BRANCH = "origin/master"
# フックが失敗した操作を書き出すログのフォルダ
LOG_DIR = Path.home() / ".local" / "state" / "rule-inject" / "logs"


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    """メインのクローンで git を実行し、結果を返す。"""
    return subprocess.run(
        ["git", "-C", str(MAIN_CLONE), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
