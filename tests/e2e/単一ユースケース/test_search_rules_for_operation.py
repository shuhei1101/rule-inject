"""単一ユースケース「操作に当たるルールを検索する」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

SEARCH_PATH = "/p/src/a.py"


def _path_index(
    make_text_file: Callable[..., Path], make_rule: Callable[..., Path]
) -> tuple[Path, Path, Path]:
    """`.py` に当たり書く操作を止めるエントリと、読む操作だけを止めるエントリを持つ索引を置く。"""
    write_rule = make_rule("write.md", "# write\n")
    read_rule = make_rule("read.md", "# read\n")
    index = make_text_file(
        "rules.yaml",
        f'rules:\n  - rule: {write_rule}\n    paths: ["**/*.py"]\n    on: [write]\n'
        f'  - rule: {read_rule}\n    paths: ["**/*.py"]\n    on: [read]\n',
    )
    return index, write_rule, read_rule


def test_normal_when_searched_by_path(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """ファイルのパスと書く操作で、当たる 2 つのルールと止めるかを受け取る（正常シナリオ）。"""
    # 準備
    index, write_rule, read_rule = _path_index(make_text_file, make_rule)
    server = serve(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(e2e_project),
        path=SEARCH_PATH,
        operation="write",
        format="json",
    )
    # 検証
    blocking = {match["rule"]: match["blocking"] for match in result.structured_content["matched"]}
    assert blocking == {str(write_rule): True, str(read_rule): False}


def test_normal_when_searched_by_tool(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """MCP のツール名と引数で、当たるルールと止めるかを受け取る（正常シナリオ）。"""
    # 準備
    rule = make_rule("docs.md", "# docs\n")
    index = make_text_file(
        "rules.yaml",
        f'rules:\n  - rule: {rule}\n    tools: ["mcp__*__write_*"]\n    args:\n      doc_path: ["dev/**"]\n    on: [mcp]\n',
    )
    server = serve(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(e2e_project),
        tool_name="mcp__plugin_docs__write_doc",
        arguments={"doc_path": "dev/設計書/設定/プラグイン"},
        format="json",
    )
    # 検証
    matched = result.structured_content["matched"]
    assert [match["rule"] for match in matched] == [str(rule)]
    assert matched[0]["blocking"] is True


def test_normal_when_no_rule_matched(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """無効のエントリだけが当たるとき、当たるルールが空で返る（正常シナリオ）。"""
    # 準備
    rule = make_rule("off.md", "# off\n")
    index = make_text_file(
        "rules.yaml",
        f'rules:\n  - rule: {rule}\n    paths: ["**/*.py"]\n    enabled: false\n',
    )
    server = serve(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(e2e_project),
        path=SEARCH_PATH,
        operation="write",
        format="json",
    )
    # 検証
    assert result.structured_content["matched"] == []


def test_error_when_both_path_and_tool(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
    tool_text: Callable[[CallToolResult], str],
) -> None:
    """パスとツール名の両方を渡すと、どちらか 1 つを渡す旨のエラーを受け取る（異常シナリオ）。"""
    # 準備
    index, _, _ = _path_index(make_text_file, make_rule)
    server = serve(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(e2e_project),
        path=SEARCH_PATH,
        operation="write",
        tool_name="mcp__plugin_docs__write_doc",
        format="json",
    )
    # 検証
    assert result.is_error is True
    assert "path" in tool_text(result)
    assert "tool_name" in tool_text(result)
