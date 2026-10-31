"""コンポジションルート。依存を作ってツールへ渡し、`MCPServer` に 7 つのツールを登録する。"""

from collections.abc import Mapping
from functools import partial
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field

from rule_inject.features.index.check import check_change, load_validator
from rule_inject.features.index.edit import IndexLocks
from rule_inject.server import check_tools, record_tools, tools
from rule_inject.server.types import ResponseFormat

# MCPServer の名前
SERVER_NAME = "rule-inject"
# `check_indexes` がプロジェクトのファイルを辿る時間の上限（秒）
UNMATCHED_SCAN_TIME_LIMIT = 30
# `check_indexes` が dev-docs への問い合わせの応答を待つ時間の上限（秒）
DEV_DOCS_TIMEOUT = 207
LIST_LIMIT_FIELD = Field(ge=1, le=tools.MAX_LIST_LIMIT)
CURSOR_FIELD = Field(pattern=tools.CURSOR_PATTERN)
POSITION_FIELD = Field(ge=0)


def build_server(
    env: Mapping[str, str],
    *,
    scan_time_limit: float = UNMATCHED_SCAN_TIME_LIMIT,
    dev_docs_timeout: float = DEV_DOCS_TIMEOUT,
) -> MCPServer:
    """依存を作ってツールへ渡し、7 つのツールを登録した `MCPServer` を返す。"""
    validator = load_validator()
    locks = IndexLocks()
    check = partial(check_change, env=env, validator=validator)
    server = MCPServer(SERVER_NAME)

    # 依存（env・validator・locks・check_change・scan_time_limit・dev_docs_timeout）を閉じ込め、引数をツールの引数だけにした関数を登録する
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

    async def check_indexes(
        project_dir: str,
        format: ResponseFormat = "markdown",
        include_global: bool = False,
        cursor: str | None = None,
    ) -> CallToolResult:
        """プロジェクトで読む索引を、フックが読めるか・JSON Schema に合うか・rule の場所にファイルがあるか・paths がプロジェクトのどのファイルにも当たらないエントリが無いか・タグのパターンが dev-docs の使われているどのタグにも当たらないエントリが無いかで確かめる。include_global でユーザー全体の索引の paths の当たらないエントリも確かめ、辿る時間の上限で止まったときは unmatched_scan.next_cursor を cursor に渡して呼び直す。dev-docs に届かないときはタグの確かめだけを飛ばし、tag_check に理由を返す。"""
        return await check_tools.check_indexes(
            project_dir=project_dir,
            format=format,
            include_global=include_global,
            cursor=cursor,
            env=env,
            validator=validator,
            scan_time_limit=scan_time_limit,
            dev_docs_timeout=dev_docs_timeout,
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

    def get_read_records(
        session_id: str | None = None,
        limit: Annotated[int, LIST_LIMIT_FIELD] = tools.DEFAULT_LIST_LIMIT,
        cursor: Annotated[str | None, CURSOR_FIELD] = None,
        format: ResponseFormat = "markdown",
    ) -> CallToolResult:
        """セッションの既読のルールごとに、今の本文が既読にした時点と同じか（current・changed・missing）と、既読の履歴に残る読んだ方法を返す。session_id を省くと、既読の記録のあるセッションの一覧を最終更新の新しい順に返す。"""
        return record_tools.get_read_records(
            session_id=session_id, limit=limit, cursor=cursor, format=format, env=env
        )

    def delete_read_records(session_id: str) -> CallToolResult:
        """セッションの既読の記録と案内済みの記録をファイルごと削除し、既読だったルールの場所を返す。削除したルールは、フックの次の呼び出しから未読として案内される。既読の履歴は削除しない。"""
        return record_tools.delete_read_records(session_id=session_id, env=env)

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    for function in (list_rules, search_rules, check_indexes, get_read_records):
        server.add_tool(function, annotations=read_only, structured_output=False)
    server.add_tool(
        write_index_entry,
        annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False),
        structured_output=False,
    )
    for destructive_function in (delete_index_entry, delete_read_records):
        server.add_tool(
            destructive_function,
            annotations=ToolAnnotations(destructive_hint=True, open_world_hint=False),
            structured_output=False,
        )
    return server
