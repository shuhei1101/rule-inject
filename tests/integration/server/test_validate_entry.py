"""インターフェース定義『索引のエントリの検査』の結合テスト。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

TIMEOUT_SEC = 30
# 子プロセスの環境から除く変数参照の名前（展開できない変数参照を再現する）
UNSET_NAME = "RULE_INJECT_TEST_UNSET"
COMMAND = Path(sys.executable).parent / "rule-inject-validate-entry"


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """配信元のフォルダ（索引のファイルとルールの本文を持つ。作業ディレクトリにする）。"""
    folder = tmp_path / "source"
    (folder / "rules").mkdir(parents=True)
    (folder / "rules" / "python.md").write_text("# 規約\n", encoding="utf-8")
    (folder / "rules.yaml").write_text(
        "rules:\n  - rule: rules/python.md\n    paths: ['**/*.py']\n", encoding="utf-8"
    )
    return folder


@pytest.fixture
def run_validate(source_dir: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """検査のコマンドを、配信元のフォルダで子プロセスとして実行する関数。"""

    def _run(stdin: str, *args: str) -> subprocess.CompletedProcess[str]:
        """標準入力と引数を指定して実行し、結果を返却する。"""
        env = {name: value for name, value in os.environ.items() if name != UNSET_NAME}
        return subprocess.run(
            [str(COMMAND), *args],
            cwd=source_dir,
            input=stdin,
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            check=False,
        )

    return _run


def test_normal(
    source_dir: Path, run_validate: Callable[..., subprocess.CompletedProcess[str]]
) -> None:
    """違反が無いエントリに空の配列を返却する（正常系）。"""
    # 準備
    before = (source_dir / "rules.yaml").read_bytes()
    # 実行
    result = run_validate("rule: rules/python.md\npaths: ['**/*.py']\n", "--index", "rules.yaml")
    # 検証
    assert result.returncode == 0
    assert json.loads(result.stdout) == []
    assert (source_dir / "rules.yaml").read_bytes() == before


def test_normal_when_schema_violated(
    source_dir: Path,
    run_validate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """スキーマの違反を場所と理由つきで返却する（正常系）。"""
    from rule_inject.features.index.check import check_index_text, load_validator

    # 準備
    text = "rule: rules/python.md\npaths: []\n"
    expected = next(
        problem.reason
        for problem in check_index_text(
            str(source_dir / "rules.yaml"),
            "rules:\n  - rule: rules/python.md\n    paths: []\n",
            {},
            validator=load_validator(),
        ).problems
        if problem.kind == "violation"
    )
    # 実行
    result = run_validate(text, "--index", "rules.yaml")
    # 検証
    assert result.returncode == 0
    violations = json.loads(result.stdout)
    assert {"path": "paths", "rule": expected} in violations


def test_normal_when_rule_file_missing(
    source_dir: Path, run_validate: Callable[..., subprocess.CompletedProcess[str]]
) -> None:
    """解決したルールの場所つきの違反を返却する（正常系）。"""
    # 実行
    result = run_validate("rule: rules/missing.md\n", "--index", "rules.yaml")
    # 検証
    assert result.returncode == 0
    assert json.loads(result.stdout) == [
        {"path": "rule", "rule": str(source_dir / "rules" / "missing.md")}
    ]


@pytest.mark.parametrize(
    ("text", "index_text"),
    [
        (
            "rule: rules/python.md\npaths: ['re:[']\n",
            "rules:\n  - rule: rules/python.md\n    paths:\n      - 're:['\n",
        ),
        ("rule: https://example.com/a.md\n", "rules:\n  - rule: https://example.com/a.md\n"),
    ],
)
def test_normal_when_entry_skipped_by_hook(
    source_dir: Path,
    run_validate: Callable[..., subprocess.CompletedProcess[str]],
    text: str,
    index_text: str,
) -> None:
    """フックが読み飛ばす理由を違反として返却する（正常系）。"""
    from rule_inject.features.index import read_index_text

    # 準備
    index_path = str(source_dir / "rules.yaml")
    expected = read_index_text(index_path, index_text, {}).outcomes[0].reason
    # 実行
    result = run_validate(text, "--index", "rules.yaml")
    # 検証
    assert result.returncode == 0
    assert json.loads(result.stdout) == [{"path": "$", "rule": expected}]


def test_normal_when_variable_unresolved(
    run_validate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """展開できない変数参照を違反にせず空の配列を返却する（正常系）。"""
    # 実行
    result = run_validate(f'rule: "!{{{UNSET_NAME}}}/python.md"\n', "--index", "rules.yaml")
    # 検証
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_error_when_input_unparsable(
    run_validate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """理由を標準エラーへ出力して終わる（異常系）。"""
    # 実行
    result = run_validate("paths: [a\n", "--index", "rules.yaml")
    # 検証
    assert result.returncode == 1
    assert "解析できません" in result.stderr


def test_error_when_index_missing(
    run_validate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """使用方法を標準エラーへ出力して終わる（異常系）。"""
    # 実行
    result = run_validate("rule: rules/python.md\n")
    # 検証
    assert result.returncode == 2
    assert "--index" in result.stderr
