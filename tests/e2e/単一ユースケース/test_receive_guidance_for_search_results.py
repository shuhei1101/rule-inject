"""単一ユースケース「検索の結果に出たファイルのルールの案内を受ける」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SEARCH_GUIDANCE = "検索で当たったファイルに未読のルールがあります"
GREP_PROMPT = (
    "Grep で {folder} の中から「{needle}」を検索し、当たったファイルの名前だけを答えてください。"
    "他のことはしないでください。"
)
FIND_PROMPT = (
    "Bash の find で {folder} の中の .txt のファイルを探し、見つかったファイルの名前だけを答えてください。"
    "他のことはしないでください。"
)


@pytest.fixture
def searched_project(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    marker: Callable[[str], str],
) -> tuple[Path, str]:
    """検索で当たる文字列を含む .txt を置き、書く操作だけを必須とするルールの索引を指す。ルールの場所と検索する文字列を返す。"""
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    needle = marker("NEEDLE")
    (e2e_project / "notes.txt").write_text(f"{needle}\n", encoding="utf-8")
    return rule, needle


def test_normal(
    e2e_project: Path,
    searched_project: tuple[Path, str],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
    guided_locations: Callable[[str], list[str]],
) -> None:
    """Grep の結果に出たファイルのルールが、止めずに案内される（正常シナリオ）。"""
    # 準備
    rule, needle = searched_project
    # 実行
    run = run_claude(GREP_PROMPT.format(folder=e2e_project, needle=needle), allow=["Grep"])
    # 検証
    assert run.denied_tools == []
    transcript = transcript_text(run.session_id)
    assert SEARCH_GUIDANCE in transcript
    assert "読むかは任意" in transcript
    assert str(rule) in transcript
    assert guided_locations(run.session_id) == [str(rule)]


def test_normal_when_bash_search(
    e2e_project: Path,
    searched_project: tuple[Path, str],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """Bash の find の結果に出たファイルのルールが、止めずに案内される（正常シナリオ）。"""
    # 準備
    rule, _ = searched_project
    # 実行
    run = run_claude(FIND_PROMPT.format(folder=e2e_project), allow=["Bash"], deny=["Grep", "Glob"])
    # 検証
    assert run.denied_tools == []
    transcript = transcript_text(run.session_id)
    assert SEARCH_GUIDANCE in transcript
    assert str(rule) in transcript


def test_normal_when_already_guided(
    e2e_project: Path,
    searched_project: tuple[Path, str],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """案内済みのルールは、同じ検索をもう一度しても案内されない（正常シナリオ）。"""
    # 準備
    _, needle = searched_project
    prompt = GREP_PROMPT.format(folder=e2e_project, needle=needle)
    first_run = run_claude(prompt, allow=["Grep"])
    guided_count = transcript_text(first_run.session_id).count(SEARCH_GUIDANCE)
    # 実行
    run = run_claude(prompt, allow=["Grep"], resume=first_run.session_id)
    # 検証
    assert guided_count == 1
    assert run.denied_tools == []
    assert transcript_text(run.session_id).count(SEARCH_GUIDANCE) == guided_count
