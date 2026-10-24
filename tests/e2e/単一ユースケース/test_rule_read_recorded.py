"""単一ユースケース「ルールを読んだことが記録される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"
DOCS_TOOL = "mcp__docs__get_doc"


def test_normal_when_read_by_bash(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
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
    history = record_history(run.session_id)
    assert len(history) == 1
    assert history[0]["method"] == "bash"
    assert history[0]["location"] == str(rule)


def test_normal_when_read_by_read_tool(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
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
    history = record_history(run.session_id)
    assert len(history) == 1
    assert history[0]["method"] == "read"
    assert history[0]["location"] == str(rule)


def test_normal_when_read_by_mcp_tool(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    docs_mcp_config: Callable[[str], Path],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
) -> None:
    """`read_by` に当たる MCP のツールで読んだルールの場所が、既読の記録と既読の履歴に載る（正常シナリオ）。"""
    # 準備
    body = "# Python の規約\n"
    rule = make_rule("python.md", body)
    configure_index(
        make_index(
            {"rule": str(rule), "read_by": [{"tools": [DOCS_TOOL], "args": {"id": ["python"]}}]}
        )
    )
    prompt = (
        "MCP のツール get_doc を、id に python を渡して 1 回だけ呼んでください。"
        "他のことはしないでください。"
    )
    # 実行
    run = run_claude(
        prompt,
        allow=[DOCS_TOOL],
        deny=["Read", "Bash", READ_RULES_TOOL],
        mcp_config=docs_mcp_config(body),
    )
    # 検証
    assert record_locations(run.session_id) == [str(rule)]
    history = record_history(run.session_id)
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["tool"] == DOCS_TOOL
    assert history[0]["location"] == str(rule)
