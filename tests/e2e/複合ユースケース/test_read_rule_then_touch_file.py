"""複合ユースケース「ルールを読んでからファイルを触る」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

WRITE_THEN_READ_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、案内に従って Read でルールの本文を読み、"
    "同じ書き込みをやり直してください。"
)
WRITE_THEN_CAT_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、案内に従って、ルールの本文を Read ではなく Bash の cat で読み、"
    "同じ書き込みをやり直してください。"
)


@pytest.fixture
def rule_and_body(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    marker: Callable[[str], str],
) -> tuple[Path, str]:
    """書く操作を必須とするルールと索引を置き、ルールのパスと本文の目印を返す。"""
    body_marker = marker("RULE-BODY")
    rule = make_rule("notes.md", f"# ノートの規約\n{body_marker}\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    return rule, body_marker


def test_normal(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """止められた書く操作が、本文を読んだ後のやり直しで通る（正常シナリオ）。"""
    # 準備
    rule, body_marker = rule_and_body
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=target),
        allow=["Write", "Edit", "Read"],
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "Read で読んでから" in run.denial_reasons[0]
    assert body_marker in "\n".join(run.tool_results.values())
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_read_by_bash(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """本文を Bash の cat で読んでも、やり直した書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, _ = rule_and_body
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_CAT_PROMPT.format(target=target),
        allow=["Write", "Edit", "Bash"],
        deny=["Read"],
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_after_compact(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """圧縮の後は、また止められ、本文を取得し直すと書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, _ = rule_and_body
    first_target = e2e_project / "first.txt"
    first_run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=first_target),
        allow=["Write", "Edit", "Read"],
        max_turns=8,
    )
    run_claude("/compact", resume=first_run.session_id, max_turns=None)
    second_target = e2e_project / "second.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=second_target),
        allow=["Write", "Edit", "Read"],
        resume=first_run.session_id,
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "hello" in second_target.read_text(encoding="utf-8")
