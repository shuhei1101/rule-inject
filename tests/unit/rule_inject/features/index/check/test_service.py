"""features/index/check/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index import load_indexes


@pytest.fixture(scope="module")
def validator() -> Any:
    """同梱の索引の JSON Schema から作った検証器（読み込みは 1 回だけ）。"""
    from rule_inject.features.index.check import load_validator

    return load_validator()


def test_load_validator() -> None:
    """同梱の Schema が Schema として正しく、書式どおりの索引を通す（正常系）。"""
    from rule_inject.features.index.check import load_validator

    # 準備
    document = {
        "default_on": ["write"],
        "rules": [
            {
                "rule": "a.md",
                "paths": ["**/*.py"],
                "exclude": ["**/tests/**"],
                "tools": ["mcp__*__create_*"],
                "args": {"kind": ["rule"]},
                "on": ["read", "write"],
                "read_by": [{"tools": ["mcp__docs__get_doc"], "args": {"path": ["*.md"]}}],
                "enabled": True,
            }
        ],
    }
    # 実行
    validator = load_validator()
    # 検証
    assert list(validator.iter_errors(document)) == []


def test_check_index_when_missing(tmp_path: Path, validator: Any) -> None:
    """無い索引を hook_error で返す（正常系）。"""
    from rule_inject.features.index.check import check_index

    # 準備
    index = tmp_path / "missing.yaml"
    # 実行
    result = check_index(str(index), {}, validator=validator)
    # 検証
    expected_reason = load_indexes([str(index)], {}).failures[0].reason
    assert result.index == str(index)
    assert [problem.kind for problem in result.problems] == ["hook_error"]
    assert result.problems[0].reason == expected_reason


def test_check_index_text(
    tmp_path: Path,
    rule_file: Callable[..., Path],
    validator: Any,
) -> None:
    """問題の無い索引では問題を返さない（正常系）。"""
    from rule_inject.features.index.check import check_index_text

    # 準備
    rule = rule_file()
    text = f"rules:\n  - rule: {rule}\n"
    # 実行
    result = check_index_text(str(tmp_path / "index.yaml"), text, {}, validator=validator)
    # 検証
    assert result.problems == ()


def test_check_index_text_when_unparsable(tmp_path: Path, validator: Any) -> None:
    """フックが読めない索引はその理由だけを返す（正常系）。"""
    from rule_inject.features.index.check import check_index_text

    # 準備
    text = "rules:\n  - rule: /r/a.md\n    paths: []\n   foo: x\n"
    # 実行
    result = check_index_text(str(tmp_path / "index.yaml"), text, {}, validator=validator)
    # 検証
    assert [problem.kind for problem in result.problems] == ["hook_error"]
    assert result.problems[0].location == "$"
    assert "4行目" in result.problems[0].reason


def test_check_index_text_when_violation(
    tmp_path: Path,
    rule_file: Callable[..., Path],
    validator: Any,
) -> None:
    """JSON Schema への違反を全て並べる（正常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.features.index.check import check_index_text

    # 準備
    rule = rule_file()
    index_path = str(tmp_path / "index.yaml")
    text = f"rules:\n  - rule: {rule}\n    paths: []\n  - rule: {rule}\n    on: []\n"
    # 実行
    result = check_index_text(index_path, text, {}, validator=validator)
    # 検証
    revs = entry_revs(text)
    assert [problem.kind for problem in result.problems] == ["violation", "violation"]
    assert [problem.location for problem in result.problems] == ["rules[0].paths", "rules[1].on"]
    assert [problem.position for problem in result.problems] == [0, 1]
    assert [problem.rev for problem in result.problems] == list(revs)


def test_check_index_text_when_missing_rule(tmp_path: Path, validator: Any) -> None:
    """ルールの場所にファイルが無いエントリを返し、無効のエントリは確かめない（正常系）。"""
    from rule_inject.features.index.check import check_index_text

    # 準備
    text = "rules:\n  - rule: /nonexistent/a.md\n  - rule: /nonexistent/b.md\n    enabled: false\n"
    # 実行
    result = check_index_text(str(tmp_path / "index.yaml"), text, {}, validator=validator)
    # 検証
    assert [problem.kind for problem in result.problems] == ["missing_rule"]
    assert result.problems[0].location == "rules[0].rule"
    assert result.problems[0].reason == "/nonexistent/a.md"


def test_check_index_text_when_skipped(tmp_path: Path, validator: Any) -> None:
    """フックが読み飛ばすエントリを返し、場所は確かめない（正常系）。"""
    from rule_inject.features.index import read_index_text
    from rule_inject.features.index.check import check_index_text

    # 準備
    index_path = str(tmp_path / "index.yaml")
    text = 'rules:\n  - rule: "!{UNSET}/a.md"\n'
    # 実行
    result = check_index_text(index_path, text, {}, validator=validator)
    # 検証
    expected_reason = read_index_text(index_path, text, {}).outcomes[0].reason
    assert [problem.kind for problem in result.problems] == ["skipped_entry"]
    assert result.problems[0].location == "rules[0]"
    assert result.problems[0].reason == expected_reason


def test_new_problems_when_existing() -> None:
    """もとからある問題は位置がずれても返さない（正常系）。"""
    from rule_inject.features.index.check.service import new_problems
    from rule_inject.features.index.check.types import IndexCheck, IndexProblem

    # 準備
    before = IndexCheck(
        index="/p/index.yaml",
        problems=(
            IndexProblem(
                kind="violation",
                location="rules[1].paths",
                reason="[] should be non-empty",
                position=1,
                rev="aaaaaaaaaaaa",
            ),
        ),
    )
    after = IndexCheck(
        index="/p/index.yaml",
        problems=(
            IndexProblem(
                kind="violation",
                location="rules[0].paths",
                reason="[] should be non-empty",
                position=0,
                rev="aaaaaaaaaaaa",
            ),
        ),
    )
    # 実行
    result = new_problems(before, after, "bbbbbbbbbbbb")
    # 検証
    assert result == ()


def test_new_problems_when_changed_entry() -> None:
    """書いたエントリの問題は書く前に同じ理由があっても返す（正常系）。"""
    from rule_inject.features.index.check.service import new_problems
    from rule_inject.features.index.check.types import IndexCheck, IndexProblem

    # 準備
    problem = IndexProblem(
        kind="violation",
        location="rules[0].paths",
        reason="[] should be non-empty",
        position=0,
        rev="bbbbbbbbbbbb",
    )
    before = IndexCheck(index="/p/index.yaml", problems=(problem,))
    after = IndexCheck(index="/p/index.yaml", problems=(problem,))
    # 実行
    result = new_problems(before, after, "bbbbbbbbbbbb")
    # 検証
    assert result == (problem,)


def test_new_problems_when_hook_error() -> None:
    """書いた後にフックが読めなければそれを返す（正常系）。"""
    from rule_inject.features.index.check.service import new_problems
    from rule_inject.features.index.check.types import IndexCheck, IndexProblem

    # 準備
    problem = IndexProblem(
        kind="hook_error",
        location="$",
        reason="3行目: 最上位のキーはインデントなしで書いてください",
        position=None,
        rev=None,
    )
    before = IndexCheck(index="/p/index.yaml", problems=(problem,))
    after = IndexCheck(index="/p/index.yaml", problems=(problem,))
    # 実行
    result = new_problems(before, after, None)
    # 検証
    assert result == (problem,)


def test_check_change(
    tmp_path: Path,
    rule_file: Callable[..., Path],
    validator: Any,
) -> None:
    """新しく出た問題を行で返す（正常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.features.index.check import check_change

    # 準備
    rule = rule_file()
    before_text = f"rules:\n  - rule: {rule}\n"
    after_text = f"rules:\n  - rule: {rule}\n    paths: []\n"
    changed_rev = entry_revs(after_text)[0]
    # 実行
    lines = check_change(
        str(tmp_path / "index.yaml"),
        before_text,
        after_text,
        changed_rev,
        env={},
        validator=validator,
    )
    # 検証
    assert len(lines) == 1
    assert lines[0].startswith("rules[0].paths: ")
