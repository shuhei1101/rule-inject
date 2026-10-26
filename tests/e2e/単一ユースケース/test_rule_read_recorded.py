"""単一ユースケース「ルールを読んだことが記録される」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

DOCS_TOOL = "mcp__docs__get_doc"
SEARCH_TOOL = "mcp__docs__search_docs"
# 本文が `# Python の規約\n` のルールの本文のハッシュ
HASH_PYTHON = "sha256:fc8f016b31191b896de55402848023f8c7a6ade80fee926650636f53fe9f58a2"
# 12 行のルールの本文（`{n} 行目` を 1 行ずつ）
LONG_BODY = "".join(f"{number} 行目\n" for number in range(1, 13))


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
    run = run_claude(prompt, allow=["Bash"], deny=["Read"])
    # 検証
    assert record_locations(run.session_id) == [f"{rule}\t{HASH_PYTHON}"]
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
    run = run_claude(prompt, allow=["Read"], deny=["Bash"])
    # 検証
    assert record_locations(run.session_id) == [f"{rule}\t{HASH_PYTHON}"]
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
        deny=["Read", "Bash"],
        mcp_config=docs_mcp_config(body),
    )
    # 検証
    assert record_locations(run.session_id) == [f"{rule}\t{HASH_PYTHON}"]
    history = record_history(run.session_id)
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["tool"] == DOCS_TOOL
    assert history[0]["location"] == str(rule)


def test_normal_when_read_by_mcp_result(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    docs_mcp_config: Callable[[str], Path],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
) -> None:
    """`scope` が `full` の文書として結果に載ったルールの場所が、`read_by` が無くても既読の記録と既読の履歴に載る（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", "# Python の規約\n")
    configure_index(make_index({"rule": str(rule)}))
    result = f'<document path="{rule}" scope="full">\n# Python の規約\n</document>'
    prompt = "MCP のツール search_docs を 1 回だけ呼んでください。他のことはしないでください。"
    # 実行
    run = run_claude(
        prompt,
        allow=[SEARCH_TOOL],
        deny=["Read", "Bash"],
        mcp_config=docs_mcp_config(result),
    )
    # 検証
    assert record_locations(run.session_id) == [f"{rule}\t{HASH_PYTHON}"]
    history = record_history(run.session_id)
    assert len(history) == 1
    assert history[0]["method"] == "mcp"
    assert history[0]["tool"] == SEARCH_TOOL
    assert history[0]["location"] == str(rule)


def test_normal_when_read_partially(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
) -> None:
    """Read で一部だけを読んだルールの場所は、既読の記録にも既読の履歴にも載らない（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", LONG_BODY)
    configure_index(make_index({"rule": str(rule)}))
    prompt = f"Read で {rule} を offset 3・limit 2 を指定して読んでください。他のことはしないでください。"
    # 実行
    run = run_claude(prompt, allow=["Read"], deny=["Bash"])
    # 検証
    assert record_locations(run.session_id) == []
    assert record_history(run.session_id) == []


def test_normal_when_mcp_result_not_full(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    docs_mcp_config: Callable[[str], Path],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    record_history: Callable[[str], list[dict[str, Any]]],
) -> None:
    """`scope` が `full` でない文書として結果に載ったルールの場所は、既読の記録にも既読の履歴にも載らない（正常シナリオ）。"""
    # 準備
    rule = make_rule("python.md", "# Python の規約\n")
    configure_index(make_index({"rule": str(rule)}))
    result = f'<document path="{rule}" scope="summary">Python の規約の説明</document>'
    prompt = "MCP のツール search_docs を 1 回だけ呼んでください。他のことはしないでください。"
    # 実行
    run = run_claude(
        prompt,
        allow=[SEARCH_TOOL],
        deny=["Read", "Bash"],
        mcp_config=docs_mcp_config(result),
    )
    # 検証
    assert record_locations(run.session_id) == []
    assert record_history(run.session_id) == []
