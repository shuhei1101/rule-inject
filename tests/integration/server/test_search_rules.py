"""インターフェース定義『ルールの検索』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

SEARCH_PATH = "/p/src/a.py"


def _path_index(tmp_path: Path, make_index: Callable[..., Path]) -> Path:
    """`.py` に当たる、`on: [write]` と `on: [read]` のエントリ（ルールの場所は別々）を持つ索引を置く。"""
    return make_index(
        f"rules:\n"
        f"  - rule: {tmp_path}/rules/write.md\n"
        f'    paths: ["**/*.py"]\n'
        f"    on: [write]\n"
        f"  - rule: {tmp_path}/rules/read.md\n"
        f'    paths: ["**/*.py"]\n'
        f"    on: [read]\n"
    )


def test_normal_when_searched_by_path(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """パスに当たる 2 つのルールを、止めるかとともに返す（正常系）。"""
    # 準備
    server = running_server(_path_index(tmp_path, make_index))
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(project_dir),
        path=SEARCH_PATH,
        operation="write",
        format="json",
    )
    # 検証
    content = result.structured_content
    blocking = {match["rule"]: match["blocking"] for match in content["matched"]}
    assert blocking == {f"{tmp_path}/rules/write.md": True, f"{tmp_path}/rules/read.md": False}
    assert content["operation"] == "write"


def test_normal_when_searched_by_tool(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """ツール名と引数に当たるルールを返す（正常系）。"""
    # 準備
    index = make_index(
        f"rules:\n"
        f"  - rule: {tmp_path}/rules/docs.md\n"
        f'    tools: ["mcp__*__write_*"]\n'
        f"    args:\n"
        f'      doc_path: ["dev/**"]\n'
        f"    on: [mcp]\n"
    )
    server = running_server(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(project_dir),
        tool_name="mcp__plugin_docs__write_doc",
        arguments={"doc_path": "dev/設計書/設定/プラグイン"},
        format="json",
    )
    # 検証
    content = result.structured_content
    assert [match["rule"] for match in content["matched"]] == [f"{tmp_path}/rules/docs.md"]
    assert content["matched"][0]["blocking"] is True
    assert content["operation"] == "mcp"


def test_normal_when_no_rule_matched(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """無効のエントリだけが当たるときは空で返す（正常系）。"""
    # 準備
    index = make_index(
        f'rules:\n  - rule: {tmp_path}/rules/off.md\n    paths: ["**/*.py"]\n    enabled: false\n'
    )
    server = running_server(index)
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(project_dir),
        path=SEARCH_PATH,
        operation="write",
        format="json",
    )
    # 検証
    assert result.structured_content["success"] is True
    assert result.structured_content["matched"] == []


def test_error_when_both_path_and_tool(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """引数の組み合わせの誤りをエラーにする（異常系）。"""
    # 準備
    server = running_server(_path_index(tmp_path, make_index))
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(project_dir),
        path=SEARCH_PATH,
        operation="write",
        tool_name="mcp__plugin_docs__write_doc",
        format="json",
    )
    # 検証
    assert result.is_error is True
    assert "path" in text_of(result)
    assert "tool_name" in text_of(result)


def test_error_when_settings_unreadable(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    invalid_config: Callable[[], str],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """呼び出しの時点で読めない設定ファイルをエラーにする（異常系）。"""
    # 準備
    server = running_server(_path_index(tmp_path, make_index))
    config = invalid_config()
    # 実行
    result = server.call(
        "search_rules",
        project_dir=str(project_dir),
        path=SEARCH_PATH,
        operation="write",
        format="json",
    )
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)
