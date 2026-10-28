"""複合ユースケース「索引のエントリを直して案内を確かめる」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SERVER = "rule-inject"
WRITE_TOOL = f"mcp__{SERVER}__write_index_entry"
SEARCH_TOOL = f"mcp__{SERVER}__search_rules"
LIST_TOOL = f"mcp__{SERVER}__list_rules"
ALLOWED_TOOLS = ["Write", "Edit", WRITE_TOOL, SEARCH_TOOL, LIST_TOOL]
DENIED_TOOLS = ["Read", "Bash"]
MAX_TURNS = 6
CREATE_PROMPT = (
    f"MCP のツール {WRITE_TOOL} を、project_dir は {{project}}、index は {{index}}、"
    'entry は rule が {rule}、paths が ["**/notes.txt"]、on が ["write"] で呼び、'
    "索引の末尾にエントリを追加してください。追加できたら「追加しました」とだけ答えてください。"
)
DISABLE_PROMPT = (
    f"MCP のツール {LIST_TOOL} を project_dir が {{project}}、format が json で呼び、"
    f"1 つ目のエントリの rev を取ってください。続けて {WRITE_TOOL} を、project_dir は {{project}}、"
    "index は {index}、position は 0、expected_rev は取った rev、entry は enabled が false で呼び、"
    "エントリを無効にしてください。無効にできたら「無効にしました」とだけ答えてください。"
)
SEARCH_PROMPT = (
    f"MCP のツール {SEARCH_TOOL} を、project_dir は {{project}}、path は {{target}}、"
    "operation は write、format は json で呼び、結果を見せてください。"
)
WRITE_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、やり直さずに、止めた案内を見せて終わってください。"
)


@pytest.fixture
def fix_environment(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_text_file: Callable[..., Path],
    serve: Callable[..., Any],
    server_mcp_config: Callable[[Any], Path],
) -> Callable[..., tuple[Path, Path, Path]]:
    """ルールの本文と索引を置いて常駐の MCP サーバーを起動し、ルール・索引・`--mcp-config` に渡す設定のパスを返す factory。"""

    def _prepare(index_entries: str) -> tuple[Path, Path, Path]:
        """index_entries（`{rule}` を持つ `rules:` の下のエントリ）を索引に書き、サーバーを起動する。"""
        rule = make_rule("notes.md", "# ノートの規約\n")
        index = make_text_file("rules/index.yaml", "rules:\n" + index_entries.format(rule=rule))
        server = serve(index)
        return rule, index, server_mcp_config(server)

    return _prepare


def test_normal_when_entry_created(
    e2e_project: Path,
    fix_environment: Callable[..., tuple[Path, Path, Path]],
    run_claude: Callable[..., Any],
) -> None:
    """ツールで作ったエントリが、検索のツールと次の書く操作の案内の両方に効く（正常シナリオ）。"""
    # 準備
    rule, index, mcp_config = fix_environment(
        '  - rule: {rule}\n    paths: ["**/*.unrelated"]\n    on: [write]\n'
    )
    target = e2e_project / "notes.txt"
    options: dict[str, Any] = {
        "allow": ALLOWED_TOOLS,
        "deny": DENIED_TOOLS,
        "mcp_config": mcp_config,
        "max_turns": MAX_TURNS,
    }
    # 実行
    created = run_claude(
        CREATE_PROMPT.format(project=e2e_project, index=index, rule=rule), **options
    )
    searched = run_claude(
        SEARCH_PROMPT.format(project=e2e_project, target=target),
        resume=created.session_id,
        **options,
    )
    written = run_claude(WRITE_PROMPT.format(target=target), resume=searched.session_id, **options)
    # 検証
    assert "**/notes.txt" in index.read_text(encoding="utf-8")
    assert any(
        str(rule) in text and '"blocking": true' in text for text in searched.tool_results.values()
    )
    assert written.denied_tools[0] == "Write"
    assert str(rule) in written.denial_reasons[0]
    assert not target.exists()


def test_normal_when_entry_disabled(
    e2e_project: Path,
    fix_environment: Callable[..., tuple[Path, Path, Path]],
    run_claude: Callable[..., Any],
) -> None:
    """ツールで無効にしたエントリは、検索のツールの結果にも次の書く操作の案内にも出ない（正常シナリオ）。"""
    # 準備
    _, index, mcp_config = fix_environment(
        '  - rule: {rule}\n    paths: ["**/notes.txt"]\n    on: [write]\n'
    )
    target = e2e_project / "notes.txt"
    options: dict[str, Any] = {
        "allow": ALLOWED_TOOLS,
        "deny": DENIED_TOOLS,
        "mcp_config": mcp_config,
        "max_turns": MAX_TURNS,
    }
    # 実行
    disabled = run_claude(DISABLE_PROMPT.format(project=e2e_project, index=index), **options)
    searched = run_claude(
        SEARCH_PROMPT.format(project=e2e_project, target=target),
        resume=disabled.session_id,
        **options,
    )
    written = run_claude(WRITE_PROMPT.format(target=target), resume=searched.session_id, **options)
    # 検証
    assert "enabled: false" in index.read_text(encoding="utf-8")
    assert any('"matched": []' in text for text in searched.tool_results.values())
    assert written.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")
