"""server/_format.py の単体テスト。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

import pytest
from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel


def _json_or_none(text: str) -> Any:
    """text が JSON ならその値を、JSON でなければ None を返す。"""
    try:
        return json.loads(text)
    except ValueError:
        return None


def _text_of(response: CallToolResult) -> str:
    """応答の先頭の content からテキストを取り出す。"""
    content = response.content[0]
    assert isinstance(content, TextContent)
    return content.text


def _entry(position: int, rule: str = "/r/a.md", paths: list[str] | None = None) -> Any:
    """効いているエントリを 1 件作る。"""
    from rule_inject.server.types import RuleEntry

    return RuleEntry(
        index="/p/rules.yaml",
        position=position,
        rev="3f9a1c0b2d4e",
        rule=rule,
        paths=paths or ["**/*.py"],
        exclude=[],
        tools=[],
        args={},
        on=["write"],
        read_by=[],
    )


def _list_result(entries: list[Any]) -> Any:
    """エントリだけを持つ一覧の応答を作る。"""
    from rule_inject.server.types import ListRulesResult

    return ListRulesResult(
        success=True,
        output="索引 1 件",
        config_path=None,
        indexes=["/p/rules.yaml"],
        entries=entries,
        unreadable_indexes=[],
        skipped_entries=[],
        disabled_entries=[],
        total=len(entries),
        next_cursor=None,
    )


@pytest.mark.parametrize(
    ("format_", "has_structured", "has_table"),
    [
        pytest.param("json", True, False, id="json"),
        pytest.param("markdown", False, True, id="markdown"),
    ],
)
def test_respond(
    format_: Literal["markdown", "json"], has_structured: bool, has_table: bool
) -> None:
    """形式ごとに structuredContent の有無を切り替える（正常系）。"""
    from rule_inject.server._format import respond
    from rule_inject.server.types import CheckIndexesResult, IndexReport, UnmatchedScanReport

    # 準備
    result = CheckIndexesResult(
        success=True,
        output="索引 1 件・問題 1 件",
        config_path="/home/user/.config/rule-inject/settings.yaml",
        problem_count=1,
        unmatched_scan=UnmatchedScanReport(
            completed=True, scanned_files=0, reason=None, next_cursor=None
        ),
        indexes=[
            IndexReport(
                index="/p/rules.yaml",
                origin="project",
                hook_error=None,
                violations=[{"location": "rules[0].paths", "reason": "[] should be non-empty"}],
                missing_rules=[],
                skipped_entries=[],
                unmatched_paths=[],
            )
        ],
    )
    # 実行
    response = respond(result, format_)
    # 検証
    text = _text_of(response)
    assert (response.structured_content is not None) is has_structured
    assert response.structured_content == _json_or_none(text)
    assert ("|" in text) is has_table


def test_render_markdown() -> None:
    """リストは表に、空のリストは「なし」にする（正常系）。"""
    from rule_inject.server._format import render_markdown

    # 準備
    result = _list_result([_entry(0), _entry(1, rule="/r/b.md")])
    # 実行
    text = render_markdown(result)
    # 検証
    entries_section = text.split("## entries")[1].split("\n## ")[0]
    table_lines = [line for line in entries_section.splitlines() if line.startswith("|")]
    assert len(table_lines) == 4
    assert re.search(r"## skipped_entries\s+なし", text)


def test_fit_page() -> None:
    """上限に収まる最大の件数を返す（正常系）。"""
    from rule_inject.server._format import MAX_RESPONSE_CHARS, fit_page, respond

    # 準備
    long_paths = ["**/" + "x" * 900 + "/*.py"]

    def build(count: int) -> BaseModel:
        """count 件のエントリを持つ一覧の応答を作る。"""
        return _list_result([_entry(index, paths=long_paths) for index in range(count)])

    # 実行
    page, count = fit_page(build, 100, "json")
    # 検証
    fitted = _text_of(respond(page, "json"))
    over = _text_of(respond(build(count + 1), "json"))
    assert 0 < count < 100
    assert len(fitted) <= MAX_RESPONSE_CHARS
    assert len(over) > MAX_RESPONSE_CHARS
