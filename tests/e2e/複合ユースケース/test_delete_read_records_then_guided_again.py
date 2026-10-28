"""複合ユースケース「既読の記録を削除して案内を受け直す」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

SERVER = "rule-inject"
GET_TOOL = f"mcp__{SERVER}__get_read_records"
DELETE_TOOL = f"mcp__{SERVER}__delete_read_records"
ALLOWED_TOOLS = ["Read", "Write", "Edit", GET_TOOL, DELETE_TOOL]
DENIED_TOOLS = ["Bash"]
MAX_TURNS = 6
READ_PROMPT = "Read で {rule} を読んでください。他のことはしないでください。"
GET_PROMPT = (
    f"MCP のツール {GET_TOOL} を session_id が {{session}}、format が json で呼び、"
    "結果を見せてください。他のことはしないでください。"
)
DELETE_PROMPT = (
    f"MCP のツール {DELETE_TOOL} を session_id が {{session}} で呼び、"
    "結果を見せてください。他のことはしないでください。"
)
WRITE_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、やり直さずに、止めた案内を見せて終わってください。"
)


def test_normal(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_text_file: Callable[..., Path],
    serve: Callable[..., Any],
    server_mcp_config: Callable[[Any], Path],
    run_claude: Callable[..., Any],
    record_history: Callable[[str], list[dict[str, Any]]],
) -> None:
    """確認のツールで既読を確かめて削除すると、次の書く操作で読んだはずのルールが未読として案内される（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    index = make_text_file(
        "rules/index.yaml",
        f'rules:\n  - rule: {rule}\n    paths: ["**/*.txt"]\n    on: [write]\n',
    )
    mcp_config = server_mcp_config(serve(index))
    target = e2e_project / "notes.txt"
    options: dict[str, Any] = {
        "allow": ALLOWED_TOOLS,
        "deny": DENIED_TOOLS,
        "mcp_config": mcp_config,
        "max_turns": MAX_TURNS,
    }
    # 実行
    read_run = run_claude(READ_PROMPT.format(rule=rule), **options)
    session = read_run.session_id
    get_run = run_claude(GET_PROMPT.format(session=session), resume=session, **options)
    delete_run = run_claude(DELETE_PROMPT.format(session=session), resume=session, **options)
    write_run = run_claude(WRITE_PROMPT.format(target=target), resume=session, **options)
    # 検証
    assert any(
        str(rule) in text and '"method": "read"' in text for text in get_run.tool_results.values()
    )
    assert any(str(rule) in text for text in delete_run.tool_results.values())
    assert write_run.denied_tools[0] == "Write"
    assert str(rule) in write_run.denial_reasons[0]
    assert not target.exists()
    assert [row["location"] for row in record_history(session)] == [str(rule)]
