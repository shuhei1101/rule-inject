"""features/guidance/service.py の単体テスト。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rule_inject.features.guidance import service
from rule_inject.features.guidance.service import (
    BLOCKING_HEADER,
    NON_BLOCKING_HEADER,
    READ_NOTE,
    READ_TOOL_NOTE,
    GUIDANCE_LIMIT,
    build_failure_notice,
    build_guidance,
    build_server_start_notice,
)
from rule_inject.features.index.types import MatchedRule, ReadTool
from rule_inject.shared.errors import IndexReadError


@pytest.fixture
def hundred_rules() -> list[MatchedRule]:
    """1 件 150 字前後の場所を持つルール 100 件（止めるものと止めないものが交互）。"""
    return [
        MatchedRule(location=f"/rules/{number:03d}/" + "x" * 137, blocking=number % 2 == 0)
        for number in range(100)
    ]


def test_build_guidance_when_blocking() -> None:
    """止める案内は止めるルールを先に並べる（正常系）。"""
    # 準備
    rules = [
        MatchedRule(location="/r/read.md", blocking=False),
        MatchedRule(location="/r/write.md", blocking=True),
    ]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.text.startswith(BLOCKING_HEADER)
    assert BLOCKING_HEADER == (
        "この操作に関連する未読のルールがあります。"
        "下のルールを参照してから、同じ操作をやり直してください。"
    )
    assert result.text.index("/r/write.md") < result.text.index("/r/read.md")


def test_build_guidance_when_not_blocking() -> None:
    """止めない案内は「やり直してください」を含まない（正常系）。"""
    # 準備
    rules = [MatchedRule(location="/r/read.md", blocking=False)]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.text.startswith(NON_BLOCKING_HEADER)
    assert NON_BLOCKING_HEADER == (
        "この操作に関連する未読のルールがあります。"
        "必要に応じて下のルールを参照してください。"
        "この案内はルールごとにセッションで 1 回だけ表示します。"
    )
    assert "やり直してください" not in result.text


def test_build_guidance_when_too_long(hundred_rules: list[MatchedRule]) -> None:
    """上限を超える分を件数にする（正常系）。"""
    # 実行
    result = build_guidance(hundred_rules, limit=10000)
    # 検証
    assert len(result.text) <= 10000
    assert re.search(r"ほか \d+ 件のルールは", result.text)


def test_build_guidance_when_shown(hundred_rules: list[MatchedRule]) -> None:
    """載せた場所だけを shown に返す（正常系）。"""
    # 実行
    result = build_guidance(hundred_rules, limit=10000)
    # 検証
    assert result.shown == tuple(re.findall(r"^- (.+)$", result.text, re.MULTILINE))
    assert 0 < len(result.shown) < 100


def test_build_guidance_when_read_tools() -> None:
    """参照するツールの行と添え書きを載せる（正常系）。"""
    # 準備
    read_tool = ReadTool(
        tool="mcp__docs__search_docs",
        args={"filter": {"field": "id", "op": "eq", "values": ["python"]}, "sections": ["命名"]},
        optional_args={},
    )
    rules = [
        MatchedRule(location="/r/a.md", blocking=True, read_tools=(read_tool,)),
        MatchedRule(location="/r/b.md", blocking=True),
    ]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.text.splitlines() == [
        BLOCKING_HEADER,
        READ_TOOL_NOTE,
        "- /r/a.md",
        '  ツール: mcp__docs__search_docs {"filter": {"field": "id", "op": "eq", "values": ["python"]}, "sections": ["命名"]}',
        "- /r/b.md",
    ]
    assert READ_TOOL_NOTE == (
        "`ツール:` の行があるルールは、そのツールで参照してください。"
        "記載の引数は全て指定し、「省略可」の引数とその他の引数は任意です。"
        "ツールが使えない場合と、`ツール:` の行が無いルールは、パスを Read で参照してください。"
    )


def test_build_guidance_when_no_read_tools() -> None:
    """参照するツールが無ければ Read の添え書きにする（正常系）。"""
    # 準備
    rules = [MatchedRule(location="/r/b.md", blocking=True)]
    # 実行
    result = build_guidance(rules)
    # 検証
    assert result.text.splitlines() == [BLOCKING_HEADER, READ_NOTE, "- /r/b.md"]
    assert READ_NOTE == "パスを Read で参照してください。"


def test_build_guidance_when_read_tool_too_long() -> None:
    """パスの行とツールの行を分けて載せない（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args={"q": "x" * 40}, optional_args={})
    rules = [
        MatchedRule(location="/r/a.md", blocking=True, read_tools=(read_tool,)),
        MatchedRule(location="/r/b.md", blocking=True, read_tools=(read_tool,)),
    ]
    # 2 件目のパスの行までは収まり、2 件目のツールの行を加えると収まらない上限
    limit = len(build_guidance(rules[:1]).text) + len("\n- /r/b.md") + 60
    # 実行
    result = build_guidance(rules, limit=limit)
    # 検証
    assert "/r/b.md" not in result.text
    assert result.text.count("ツール: ") == 1
    assert re.search(r"ほか 1 件のルールは", result.text)
    assert result.shown == ("/r/a.md",)


def test_build_guidance_when_tool_rule_omitted() -> None:
    """ツールの行を載せなければ Read の添え書きにする（正常系）。"""
    # 準備
    read_tool = ReadTool(tool="mcp__docs__search_docs", args={"q": "x" * 200}, optional_args={})
    rules = [
        MatchedRule(location="/r/a.md", blocking=True),
        MatchedRule(location="/r/b.md", blocking=True, read_tools=(read_tool,)),
    ]
    # 1 件目と件数の行だけが収まる上限
    limit = len(BLOCKING_HEADER) + len(READ_TOOL_NOTE) + 120
    # 実行
    result = build_guidance(rules, limit=limit)
    # 検証
    assert result.text.splitlines()[1] == READ_NOTE
    assert READ_TOOL_NOTE not in result.text
    assert result.shown == ("/r/a.md",)


def test_tool_line() -> None:
    """書いた順の JSON にする（正常系）。"""
    # 準備
    ordered = ReadTool(
        tool="mcp__docs__search_docs",
        args={"sections": ["命名"], "filter": {"field": "id"}},
        optional_args={},
    )
    empty = ReadTool(tool="mcp__docs__search_docs", args={}, optional_args={})
    optional = ReadTool(
        tool="mcp__docs__search_docs",
        args={"filter": {"field": "id"}},
        optional_args={"sections": ["命名"]},
    )
    # 実行
    lines = [service._tool_line(ordered), service._tool_line(empty), service._tool_line(optional)]
    # 検証
    assert lines == [
        '  ツール: mcp__docs__search_docs {"sections": ["命名"], "filter": {"field": "id"}}',
        "  ツール: mcp__docs__search_docs {}",
        '  ツール: mcp__docs__search_docs {"filter": {"field": "id"}}（省略可: {"sections": ["命名"]}）',
    ]


def test_build_failure_notice() -> None:
    """場所と理由を並べる（正常系）。"""
    # 準備
    errors = [
        IndexReadError(path="/i/a.yaml", reason="FileNotFoundError: no such file"),
        IndexReadError(path="/i/b.yaml", reason="ValueError: 3行目: 許さないキー"),
    ]
    # 実行
    result = build_failure_notice("索引を読めませんでした", errors, Path("/s/rule-inject.log"))
    # 検証
    assert "索引を読めませんでした" in result
    assert "- /i/a.yaml: FileNotFoundError: no such file" in result
    assert "- /i/b.yaml: ValueError: 3行目: 許さないキー" in result
    assert "/s/rule-inject.log" in result


def test_build_search_guidance() -> None:
    """読むかは任意と伝える案内にする（正常系）。"""
    # 実行
    result = service.build_search_guidance(
        [
            MatchedRule(location="/r/a.md", blocking=False),
            MatchedRule(location="/r/b.md", blocking=False),
        ]
    )
    # 検証
    assert result.text.startswith(service.SEARCH_HEADER)
    assert service.SEARCH_HEADER == (
        "検索結果のファイルに関連する未読のルールがあります（参照は任意です）。"
        "この案内はルールごとにセッションで 1 回だけ表示します。"
    )
    assert "- /r/a.md" in result.text
    assert "- /r/b.md" in result.text
    assert "やり直してください" not in result.text
    assert result.shown == ("/r/a.md", "/r/b.md")


def test_build_search_guidance_when_unchecked() -> None:
    """照合しなかった件数を添える（正常系）。"""
    # 実行
    result = service.build_search_guidance(
        [MatchedRule(location="/r/a.md", blocking=False)], unchecked=5
    )
    # 検証
    assert result.text.rstrip().endswith("検索結果のうち 5 件は照合していません。")


def test_build_search_guidance_when_too_long(hundred_rules: list[MatchedRule]) -> None:
    """上限を超える分を件数にする（正常系）。"""
    # 実行
    result = service.build_search_guidance(hundred_rules, limit=10000)
    # 検証
    assert len(result.text) <= 10000
    assert re.search(r"ほか \d+ 件のルールは", result.text)
    assert result.shown == tuple(re.findall(r"^- (.+)$", result.text, re.MULTILINE))
    assert 0 < len(result.shown) < 100


def test_build_search_guidance_when_read_tools() -> None:
    """参照するツールの行と添え書きを載せる（正常系）。"""
    # 準備
    read_tool = ReadTool(
        tool="mcp__docs__search_docs",
        args={"filter": {"field": "id", "op": "eq", "values": ["python"]}},
        optional_args={},
    )
    rules = [MatchedRule(location="/r/a.md", blocking=False, read_tools=(read_tool,))]
    # 実行
    result = service.build_search_guidance(rules)
    # 検証
    assert result.text.splitlines() == [
        service.SEARCH_HEADER,
        READ_TOOL_NOTE,
        "- /r/a.md",
        '  ツール: mcp__docs__search_docs {"filter": {"field": "id", "op": "eq", "values": ["python"]}}',
    ]


def test_build_server_start_notice() -> None:
    """サービス名と接続し直す方法を載せる（正常系）。"""
    # 実行
    notice = build_server_start_notice("rule-inject-ut")
    # 検証
    assert "rule-inject-ut" in notice
    assert "/mcp" in notice
    assert len(notice) <= GUIDANCE_LIMIT
