"""単一ユースケース「圧縮で既読の記録が捨てられる」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def test_normal(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    guided_locations: Callable[[str], list[str]],
) -> None:
    """手動の圧縮で、そのセッションの既読の記録と案内済みの記録が捨てられる（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", "# Python の規約\n")
    guided_rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(
        make_index(
            {"rule": str(rule)},
            {"rule": str(guided_rule), "paths": ["**/*.txt"], "on": ["write"]},
        )
    )
    read_prompt = (
        f"MCP のツール read_rules を 1 回だけ呼んでください。locations に {rule} を渡し、"
        "session_id は渡さないでください。"
    )
    read_run = run_claude(read_prompt, allow=[READ_RULES_TOOL])
    target = e2e_project / "notes.txt"
    target.write_text("notes\n", encoding="utf-8")
    guided_run = run_claude(
        f"Read で {target} を読み、「読んだ」とだけ答えてください。他のことはしないでください。",
        allow=["Read"],
        resume=read_run.session_id,
    )
    assert record_locations(read_run.session_id) == [str(rule)]
    assert guided_locations(guided_run.session_id) == [str(guided_rule)]
    # 実行
    run_claude("/compact", resume=read_run.session_id, max_turns=None)
    # 検証
    assert record_locations(read_run.session_id) == []
    assert guided_locations(read_run.session_id) == []
