"""索引のエントリの検査のコマンド（project-index の `validators[]` から呼ばれる `rule-inject-validate-entry`）。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rule_inject.features.index.check.service import check_entry, load_validator
from rule_inject.shared.errors import describe

# 標準入力を解析できないときの終了コード（インターフェース定義「索引のエントリの検査」）
FAILURE_EXIT_CODE = 1
PROGRAM_NAME = "rule-inject-validate-entry"


def main(argv: Sequence[str] | None = None) -> int:
    """`--index` と標準入力のエントリを読み取り、違反の JSON の配列を標準出力へ出力する。"""
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME, description="索引のエントリ 1 件を検査し、違反を JSON の配列で出力する"
    )
    parser.add_argument("--index", required=True, help="索引のファイルのパス")
    args = parser.parse_args(argv)
    try:
        entry = YAML(typ="safe").load(sys.stdin.read())
    except YAMLError as exc:
        print(f"標準入力を YAML として解析できません: {describe(exc)}", file=sys.stderr)
        return FAILURE_EXIT_CODE
    if not isinstance(entry, dict):
        print("標準入力がエントリのマップではありません", file=sys.stderr)
        return FAILURE_EXIT_CODE
    index_path = str(Path(args.index).absolute())
    problems = check_entry(index_path, entry, os.environ, validator=load_validator())
    violations = [{"path": problem.location, "rule": problem.reason} for problem in problems]
    print(json.dumps(violations, ensure_ascii=False))
    return 0
