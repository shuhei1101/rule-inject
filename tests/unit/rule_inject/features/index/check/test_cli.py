"""features/index/check/cli.py の単体テスト。"""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index.check import cli
from rule_inject.features.index.check.types import IndexProblem


def test_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """問題を違反の JSON の配列で出力し、終了コード 0 を返却する（正常系）。"""
    # 準備
    calls: list[tuple[str, Mapping[str, object]]] = []
    problem = IndexProblem(kind="violation", location="paths", reason="理由", position=0, rev="r")

    def _check_entry(
        index_path: str, entry: Mapping[str, object], env: Mapping[str, str], *, validator: Any
    ) -> tuple[IndexProblem, ...]:
        calls.append((index_path, entry))
        return (problem,)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "check_entry", _check_entry)
    monkeypatch.setattr(sys, "stdin", io.StringIO("rule: a.md\n"))
    # 実行
    code = cli.main(["--index", "rules.yaml"])
    # 検証
    assert code == 0
    assert json.loads(capsys.readouterr().out) == [{"path": "paths", "rule": "理由"}]
    assert calls == [(str(tmp_path / "rules.yaml"), {"rule": "a.md"})]


@pytest.mark.parametrize("text", ["paths: [a\n", "- a\n"])
def test_main_when_unparsable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    text: str,
) -> None:
    """標準入力を解析できない（異常系）。"""
    # 準備
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    # 実行
    code = cli.main(["--index", "rules.yaml"])
    # 検証
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err != ""
    assert captured.out == ""


def test_main_when_index_missing(capsys: pytest.CaptureFixture[str]) -> None:
    """`--index` が無い（異常系）。"""
    # 実行
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])
    # 検証
    assert exc_info.value.code == 2
    assert "--index" in capsys.readouterr().err
