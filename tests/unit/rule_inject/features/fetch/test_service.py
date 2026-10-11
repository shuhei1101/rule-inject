"""features/fetch/service.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from rule_inject.features.fetch import service
from rule_inject.features.fetch.client import FetchError
from rule_inject.features.fetch.service import collect_pages, render_result
from rule_inject.features.fetch.types import FetchFailure, ReadRulesResult, RulePage

WEB_URL = "https://example.com/rules/web.md"


@pytest.fixture
def make_fetch() -> Callable[..., tuple[Callable[[str, float], str], list[tuple[str, float]]]]:
    """呼び出しを記録し、決めた本文を返す URL 取得の関数を作る factory。"""

    def _make(
        body: str = "# Web の規約\n",
    ) -> tuple[Callable[[str, float], str], list[tuple[str, float]]]:
        """本文を返す fetch と、その呼び出しの記録を返す。"""
        calls: list[tuple[str, float]] = []

        def _fetch(url: str, timeout: float) -> str:
            """呼び出しを記録して本文を返す。"""
            calls.append((url, timeout))
            return body

        return _fetch, calls

    return _make


def _failing_fetch(url: str, timeout: float) -> str:
    """常に取得の失敗を送出する。"""
    raise FetchError(path=url, reason="HTTP 500")


def test_collect_pages(
    rule_file: Callable[..., Path],
    make_fetch: Callable[..., tuple[Callable[[str, float], str], list[tuple[str, float]]]],
) -> None:
    """ローカルの本文を返す（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    fetch, calls = make_fetch()
    # 実行
    result = collect_pages([str(rule)], fetch=fetch)
    # 検証
    assert result.pages == [RulePage(location=str(rule), body="# Python の規約\n")]
    assert calls == []


def test_collect_pages_when_url(
    make_fetch: Callable[..., tuple[Callable[[str, float], str], list[tuple[str, float]]]],
) -> None:
    """URL を fetch で取得する（正常系）。"""
    # 準備
    fetch, calls = make_fetch("# Web の規約\n")
    # 実行
    result = collect_pages([WEB_URL], fetch=fetch)
    # 検証
    assert result.pages == [RulePage(location=WEB_URL, body="# Web の規約\n")]
    assert calls == [(WEB_URL, 1.0)]


def test_collect_pages_when_given_failures(rule_file: Callable[..., Path]) -> None:
    """呼び出し元の failures を先頭に載せる（正常系）。"""
    # 準備
    rule = rule_file()
    given = FetchFailure(location="/r/unlisted.md", reason="索引に載っていない場所")
    # 実行
    result = collect_pages([str(rule)], failures=[given])
    # 検証
    assert result.failures[0] == given
    assert len(result.pages) == 1


def test_collect_pages_when_over_limit(rule_file: Callable[..., Path]) -> None:
    """上限を超える本文を deferred へ回す（正常系）。"""
    # 準備
    first = rule_file("a.md", "a" * 50)
    second = rule_file("b.md", "b" * 50)
    one_page_and_deferred = ReadRulesResult(
        pages=[RulePage(location=str(first), body="a" * 50)],
        deferred=[str(second)],
        failures=[],
    )
    limit = len(render_result(one_page_and_deferred))
    # 実行
    result = collect_pages([str(first), str(second)], limit=limit)
    # 検証
    assert result.pages == [RulePage(location=str(first), body="a" * 50)]
    assert result.deferred == [str(second)]
    assert len(render_result(result)) <= limit


def test_collect_pages_when_single_over_limit(rule_file: Callable[..., Path]) -> None:
    """1 件で上限を超える本文は failures へ回す（正常系）。"""
    # 準備
    large = rule_file("large.md", "x" * 200)
    # 実行
    result = collect_pages([str(large)], limit=100)
    # 検証
    assert result.pages == []
    assert result.deferred == []
    assert len(result.failures) == 1
    assert "上限" in result.failures[0].reason


def test_collect_pages_when_none_fit_with_others(rule_file: Callable[..., Path]) -> None:
    """1 件も載せられないときは進む形で failures へ回す（正常系）。"""
    # 準備
    first = rule_file("a.md", "a" * 50)
    second = rule_file("b.md", "b" * 50)
    third = rule_file("c.md", "c" * 50)
    single_page = ReadRulesResult(pages=[RulePage(location=str(first), body="a" * 50)])
    limit = len(render_result(single_page))
    # 実行
    result = collect_pages([str(first), str(second), str(third)], limit=limit)
    # 検証
    assert result.pages == []
    assert result.deferred == []
    assert len(result.failures) == 3
    assert "取り直す" in result.failures[0].reason
    assert "取り直す" in result.failures[1].reason
    assert "取り直す" in result.failures[2].reason


def test_collect_pages_when_fetch_failed(tmp_path: Path) -> None:
    """取得できない場所を failures へ回す（正常系）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    # 実行
    result = collect_pages([str(missing), WEB_URL], fetch=_failing_fetch)
    # 検証
    assert result.pages == []
    assert len(result.failures) == 2


def test_render_result() -> None:
    """3 つのキーを持ち、日本語をエスケープしない JSON にする（正常系）。"""
    # 準備
    result = ReadRulesResult(
        pages=[RulePage(location="/r/a.md", body="日本語の本文")],
        deferred=["/r/b.md"],
        failures=[FetchFailure(location="/r/c.md", reason="HTTP 404")],
    )
    # 実行
    text = render_result(result)
    # 検証
    assert set(json.loads(text)) == {"pages", "deferred", "failures"}
    assert "日本語の本文" in text


def test_collect_pages_when_body_has_variables(rule_file: Callable[..., Path]) -> None:
    """展開した本文を返し、展開後の字数で上限を数える（正常系）。"""
    # 準備
    rule = rule_file("var.md", "!{X}")
    env = {"X": "x" * 200}
    before_expansion = ReadRulesResult(pages=[RulePage(location=str(rule), body="!{X}")])
    limit = len(render_result(before_expansion))
    # 実行
    over_limit = collect_pages([str(rule)], env=env, limit=limit)
    within_limit = collect_pages([str(rule)], env=env)
    # 検証
    assert over_limit.pages == []
    assert len(over_limit.failures) == 1
    assert "上限" in over_limit.failures[0].reason
    assert within_limit.pages == [RulePage(location=str(rule), body="x" * 200)]


def test_expand_body() -> None:
    """全て展開できれば注釈を足さない（正常系）。"""
    # 実行
    result = service.expand_body("# A\n!{X}", {"X": "1"})
    # 検証
    assert result == "# A\n1"


def test_expand_body_when_unset() -> None:
    """展開できない名前を注釈で知らせる（正常系）。"""
    # 実行
    result = service.expand_body("!{B} !{X} !{A} !{B}", {"X": "1"})
    # 検証
    assert result.splitlines() == [
        "> 注釈: 次の変数参照は、環境変数が設定されていないため展開していない: B、A",
        "!{B} 1 !{A} !{B}",
    ]
