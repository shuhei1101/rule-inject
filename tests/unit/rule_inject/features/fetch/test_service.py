"""features/fetch/service.py の単体テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.fetch.client import FetchError
from rule_inject.features.fetch.service import ToolArgumentError, read_rules, render_result
from rule_inject.features.fetch.types import FetchFailure, ReadRulesResult, RulePage
from rule_inject.shared.errors import RecordWriteError

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


def test_read_rules(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """場所で引いて既読にする（正常系）。"""
    # 準備
    rule = rule_file("python.md", "# Python の規約\n")
    entries = [make_entry(str(rule))]
    # 実行
    result = read_rules([str(rule)], [], session_id, entries=entries, state_dir=state_dir)
    # 検証
    assert result.pages == [RulePage(location=str(rule), body="# Python の規約\n")]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(rule)]


def test_read_rules_when_by_path(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
) -> None:
    """対象のパスで引く（正常系）。"""
    # 準備
    py_rule = rule_file("python.md", "# Python の規約\n")
    ts_rule = rule_file("typescript.md", "# TypeScript の規約\n")
    entries = [
        make_entry(str(py_rule), paths=["**/*.py"]),
        make_entry(str(ts_rule), paths=["**/*.ts"]),
    ]
    # 実行
    result = read_rules([], ["/p/src/a.py"], session_id, entries=entries, state_dir=state_dir)
    # 検証
    assert result.pages == [RulePage(location=str(py_rule), body="# Python の規約\n")]


def test_read_rules_when_url(
    state_dir: Path,
    session_id: str,
    make_entry: Callable[..., Any],
    make_fetch: Callable[..., Any],
) -> None:
    """URL を fetch で取得する（正常系）。"""
    # 準備
    fetch, calls = make_fetch("# Web の規約\n")
    entries = [make_entry(WEB_URL)]
    # 実行
    result = read_rules(
        [WEB_URL], [], session_id, entries=entries, state_dir=state_dir, fetch=fetch
    )
    # 検証
    assert result.pages == [RulePage(location=WEB_URL, body="# Web の規約\n")]
    assert calls == [(WEB_URL, 1.0)]


def test_read_rules_when_not_in_index(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    make_fetch: Callable[..., Any],
) -> None:
    """索引に無い場所は読まない（正常系）。"""
    # 準備
    listed = rule_file("listed.md")
    unlisted = rule_file("unlisted.md")
    fetch, calls = make_fetch()
    entries = [make_entry(str(listed))]
    # 実行
    result = read_rules(
        [str(unlisted), WEB_URL], [], session_id, entries=entries, state_dir=state_dir, fetch=fetch
    )
    # 検証
    assert result.pages == []
    assert len(result.failures) == 2
    assert "索引に載っていない場所" in result.failures[0].reason
    assert "索引に載っていない場所" in result.failures[1].reason
    assert calls == []


def test_read_rules_when_over_limit(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """上限を超える本文を deferred へ回す（正常系）。"""
    # 準備
    first = rule_file("a.md", "a" * 50)
    second = rule_file("b.md", "b" * 50)
    entries = [make_entry(str(first)), make_entry(str(second))]
    one_page_and_deferred = ReadRulesResult(
        pages=[RulePage(location=str(first), body="a" * 50)],
        deferred=[str(second)],
        failures=[],
    )
    limit = len(render_result(one_page_and_deferred))
    # 実行
    result = read_rules(
        [str(first), str(second)],
        [],
        session_id,
        entries=entries,
        state_dir=state_dir,
        limit=limit,
    )
    # 検証
    assert result.pages == [RulePage(location=str(first), body="a" * 50)]
    assert result.deferred == [str(second)]
    assert read_lines(state_dir / f"{session_id}.txt") == [str(first)]


def test_read_rules_when_single_over_limit(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
) -> None:
    """1 件で上限を超える本文は failures へ回す（正常系）。"""
    # 準備
    large = rule_file("large.md", "x" * 200)
    entries = [make_entry(str(large))]
    # 実行
    result = read_rules(
        [str(large)], [], session_id, entries=entries, state_dir=state_dir, limit=100
    )
    # 検証
    assert result.pages == []
    assert result.deferred == []
    assert len(result.failures) == 1
    assert "上限" in result.failures[0].reason


def test_read_rules_when_fetch_failed(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    make_entry: Callable[..., Any],
) -> None:
    """取得できない場所を failures へ回して既読にしない（正常系）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    entries = [make_entry(str(missing)), make_entry(WEB_URL)]
    # 実行
    result = read_rules(
        [str(missing), WEB_URL],
        [],
        session_id,
        entries=entries,
        state_dir=state_dir,
        fetch=_failing_fetch,
    )
    # 検証
    assert result.pages == []
    assert len(result.failures) == 2
    assert not (state_dir / f"{session_id}.txt").exists()


def test_read_rules_when_no_session_id(
    state_dir: Path,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
) -> None:
    """session_id が無ければ ToolArgumentError にする（異常系）。"""
    # 準備
    rule = rule_file()
    entries = [make_entry(str(rule))]
    # 実行・検証
    with pytest.raises(ToolArgumentError, match="session_id"):
        read_rules([str(rule)], [], None, entries=entries, state_dir=state_dir)


def test_read_rules_when_no_target(state_dir: Path, session_id: str) -> None:
    """引く対象が無ければ ToolArgumentError にする（異常系）。"""
    # 実行・検証
    with pytest.raises(ToolArgumentError, match="locations"):
        read_rules([], [], session_id, entries=[], state_dir=state_dir)


def test_read_rules_when_record_unwritable(
    state_dir: Path,
    session_id: str,
    rule_file: Callable[..., Path],
    make_entry: Callable[..., Any],
    unwritable: Callable[[Path, int], Path],
) -> None:
    """記録に書けなければ RecordWriteError にする（異常系）。"""
    # 準備
    rule = rule_file()
    entries = [make_entry(str(rule))]
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    # 実行・検証
    with pytest.raises(RecordWriteError):
        read_rules([str(rule)], [], session_id, entries=entries, state_dir=state_dir)


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
