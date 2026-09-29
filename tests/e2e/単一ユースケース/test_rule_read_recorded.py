"""単一ユースケース「ルールを読んだことが記録される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def test_normal_when_read_by_bash(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
) -> None:
    """Bash の cat で読んだルールの場所が、既読の記録に載る（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", "# Python の規約\n")
    configure_index(make_index({"rule": str(rule)}))
    prompt = f"Bash の cat で {rule} を読んでください。他のことはしないでください。"
    # 実行
    run = run_claude(prompt, allow=["Bash"], deny=["Read", READ_RULES_TOOL])
    # 検証
    assert record_locations(run.session_id) == [str(rule)]


def test_normal_when_read_by_read_tool(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
) -> None:
    """Read で読んだルールの場所が、既読の記録に載る（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", "# Python の規約\n")
    configure_index(make_index({"rule": str(rule)}))
    prompt = f"Read で {rule} を読んでください。他のことはしないでください。"
    # 実行
    run = run_claude(prompt, allow=["Read"], deny=["Bash", READ_RULES_TOOL])
    # 検証
    assert record_locations(run.session_id) == [str(rule)]
