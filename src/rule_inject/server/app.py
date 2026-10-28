"""コンポジションルート。依存を作ってツールへ渡し、`MCPServer` に 5 つのツールを登録する。"""

from collections.abc import Mapping
from functools import partial
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field

from rule_inject.features.index.check import check_change, load_validator
from rule_inject.features.index.edit import IndexLocks
from rule_inject.server import tools
from rule_inject.server.types import ResponseFormat

# MCPServer の名前
SERVER_NAME = "rule-inject"
LIST_LIMIT_FIELD = Field(ge=1, le=tools.MAX_LIST_LIMIT)
CURSOR_FIELD = Field(pattern=tools.CURSOR_PATTERN)
POSITION_FIELD = Field(ge=0)


def build_server(env: Mapping[str, str]) -> MCPServer:
    """依存を作ってツールへ渡し、5 つのツールを登録した `MCPServer` を返す。"""
    validator = load_validator()
    locks = IndexLocks()
    check = partial(check_change, env=env, validator=validator)
    server = MCPServer(SERVER_NAME)

    # 依存（env・validator・locks・check_change）を閉じ込め、引数をツールの引数だけにした関数を登録する
    # （partial で渡すと、依存の引数がツールの引数の Schema に残るため）
    def list_rules(
        project_dir: str,
        limit: Annotated[int, LIST_LIMIT_FIELD] = tools.DEFAULT_LIST_LIMIT,
        cursor: Annotated[str | None, CURSOR_FIELD] = None,
        format: ResponseFormat = "markdown",
    ) -> CallToolResult:
        """プロジェクトで今効いているルール（読む索引とエントリ）と、読めなかった索引・読み飛ばしたエントリ・無効のエントリを返す。"""
        return tools.list_rules(
            project_dir=project_dir, limit=limit, cursor=cursor, format=format, env=env
        )

    def search_rules(
        project_dir: str,
        path: str | None = None,
        operation: Literal["read", "write"] | None = None,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        format: ResponseFormat = "markdown",
    ) -> CallToolResult:
        """ファイルのパス（operation とともに）か MCP のツールの呼び出し（tool_name と arguments）に当たるルールと、未読のときに操作を止めるかを返す。"""
        return tools.search_rules(
            project_dir=project_dir,
            path=path,
            operation=operation,
            tool_name=tool_name,
            arguments=arguments,
            format=format,
            env=env,
        )

    def check_indexes(project_dir: str, format: ResponseFormat = "markdown") -> CallToolResult:
        """プロジェクトで読む索引を、フックが読めるか・JSON Schema に合うか・rule の場所にファイルがあるかで確かめる。"""
        return tools.check_indexes(
            project_dir=project_dir, format=format, env=env, validator=validator
        )

    def write_index_entry(
        project_dir: str,
        index: str,
        entry: dict[str, Any],
        position: Annotated[int | None, POSITION_FIELD] = None,
        expected_rev: str | None = None,
        remove_keys: list[str] | None = None,
        dry_run: bool = False,
    ) -> CallToolResult:
        """設定ファイルで読む索引に、エントリを末尾へ新規作成する（position なし）か、位置で指したエントリのキーを書き換える（position と expected_rev）。書いた後の索引に新しい問題が出るときは書き込まない。"""
        return tools.write_index_entry(
            project_dir=project_dir,
            index=index,
            entry=entry,
            position=position,
            expected_rev=expected_rev,
            remove_keys=remove_keys,
            dry_run=dry_run,
            env=env,
            locks=locks,
            check_change=check,
        )

    def delete_index_entry(
        project_dir: str,
        index: str,
        position: Annotated[int, POSITION_FIELD],
        expected_rev: str,
        dry_run: bool = False,
    ) -> CallToolResult:
        """設定ファイルで読む索引から、位置と expected_rev で指したエントリを削除する。"""
        return tools.delete_index_entry(
            project_dir=project_dir,
            index=index,
            position=position,
            expected_rev=expected_rev,
            dry_run=dry_run,
            env=env,
            locks=locks,
        )

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    for function in (list_rules, search_rules, check_indexes):
        server.add_tool(function, annotations=read_only, structured_output=False)
    server.add_tool(
        write_index_entry,
        annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False),
        structured_output=False,
    )
    server.add_tool(
        delete_index_entry,
        annotations=ToolAnnotations(destructive_hint=True, open_world_hint=False),
        structured_output=False,
    )
    return server
