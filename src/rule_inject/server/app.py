"""コンポジションルート。依存を作ってツールへ引き渡し、`MCPServer` に 11 のツールを登録する。"""

from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field

from rule_inject.features.index.check import check_change, load_validator
from rule_inject.features.index.edit import IndexLocks
from rule_inject.server import admin_tools, check_tools, record_tools, tools
from rule_inject.server.clone import RunCommand, run_command
from rule_inject.server.control import ServerControl
from rule_inject.server.types import ResponseFormat

# MCPServer の名前
SERVER_NAME = "rule-inject"
# 接続時の initialize の応答で返却する instructions（新しいファイルの作り方の決まりと、MCP のツールの選び方）
SERVER_INSTRUCTIONS = (
    "rule-inject は、Claude Code がファイルを触る前に、そのファイルに該当する未読のルールを案内する。"
    "新しいファイルは Write で空の内容で作った時点でそのファイルに該当するルールが案内されるため、"
    "案内されたルールを参照してから Edit で中身を記載する。"
    # 呼ぶ場面: 作業の分類ごとにツール名を対応づける
    "この MCP のツールは、ルールと索引そのものを扱う作業で呼ぶ。"
    "有効なルールの一覧は list_rules、"
    "ファイルやツールの呼び出しにヒットするルールの検索は search_rules、"
    "索引のエントリの編集と索引のチェックは write_index_entry・delete_index_entry・check_indexes、"
    "既読の記録の確認と削除は get_read_records・delete_read_records、"
    "設定ファイルを書き換えた後の再読込とサーバーの状態の確認・再起動・更新は"
    " reload_settings・get_server_status・restart_server・update_server で行う。"
    # 呼ばない場面: grep・Read で足りる作業と、grep・Read・Edit の代わりにツールを呼ぶ作業
    "ルールの本文は、案内された場所を Read で参照する。"
    "プロジェクトのコードや文書は grep・Read で探す。"
    "どのルールがヒットするかは、索引を grep・Read せずに search_rules で調べる。"
    "索引は Edit で編集せず、write_index_entry・delete_index_entry で編集する。"
    # ツール間の順序
    "エントリを書き換え・削除する前に、list_rules で position と rev を取得する。"
    "ルールが案内されないときは、search_rules でヒットするかを確認してから、"
    "get_read_records で既読かを確認する。"
)
# `check_indexes` がプロジェクトのファイルを辿る時間の上限（秒）
UNMATCHED_SCAN_TIME_LIMIT = 30
# `check_indexes` が project-index への問い合わせの応答を待つ時間の上限（秒）
DEV_DOCS_TIMEOUT = 207
LIST_LIMIT_FIELD = Field(ge=1, le=tools.MAX_LIST_LIMIT)
CURSOR_FIELD = Field(pattern=tools.CURSOR_PATTERN)
POSITION_FIELD = Field(ge=0)


def build_server(
    env: Mapping[str, str],
    *,
    control: ServerControl,
    clone: Path,
    run_command: RunCommand = run_command,
    scan_time_limit: float = UNMATCHED_SCAN_TIME_LIMIT,
    dev_docs_timeout: float = DEV_DOCS_TIMEOUT,
) -> MCPServer:
    """依存を作ってツールへ引き渡し、11 のツールを登録した `MCPServer` を返却する。"""
    validator = load_validator()
    locks = IndexLocks()
    check = partial(check_change, env=env, validator=validator)
    server = MCPServer(SERVER_NAME, instructions=SERVER_INSTRUCTIONS)

    # 依存（env・validator・locks・check_change・scan_time_limit・dev_docs_timeout・control・clone・run_command）を閉じ込め、引数をツールの引数だけにした関数を登録する
    # （partial で引き渡すと、依存の引数がツールの引数の Schema に残るため）
    def list_rules(
        project_dir: str,
        limit: Annotated[int, LIST_LIMIT_FIELD] = tools.DEFAULT_LIST_LIMIT,
        cursor: Annotated[str | None, CURSOR_FIELD] = None,
        format: ResponseFormat = "markdown",
    ) -> CallToolResult:
        """プロジェクトで有効なルール（読む索引とエントリ）と、読めなかった索引・読み飛ばしたエントリ・無効のエントリを返却する。"""
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
        """ファイルのパス（operation とともに）か MCP のツールの呼び出し（tool_name と arguments）に該当するルールと、未読のときに操作を止めるかを返却する。"""
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
        """プロジェクトで読む索引を、フックが読めるか・JSON Schema に合うか・rule の場所にファイルがあるか・paths がプロジェクトのどのファイルにも該当しないエントリが無いか・タグのパターンが project-index の使用中のどのタグにも該当しないエントリが無いかで確認する。include_global でユーザー全体の索引の paths の該当しないエントリも確認し、辿る時間の上限で止まったときは unmatched_scan.next_cursor を cursor に引き渡して再度呼び出す。project-index に届かないときはタグの確認だけを飛ばし、tag_check に理由を返却する。"""
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
        """設定ファイルで読む索引に、エントリを末尾へ新規作成する（position なし）か、位置で指したエントリのキーを書き換える（position と expected_rev）。書き込んだ後の索引に新しい問題が出るときは書き込まない。"""
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
        """セッションの既読のルールごとに、今の本文が既読にした時点と同じか（current・changed・missing）と、既読の履歴に残る読んだ方法を返却する。session_id を省くと、既読の記録のあるセッションの一覧を最終更新の新しい順に返却する。"""
        return record_tools.get_read_records(
            session_id=session_id, limit=limit, cursor=cursor, format=format, env=env
        )

    def delete_read_records(session_id: str) -> CallToolResult:
        """セッションの既読の記録と案内済みの記録をファイルごと削除し、既読だったルールの場所を返却する。削除したルールは、フックの次の呼び出しから未読として案内される。既読の履歴は削除しない。"""
        return record_tools.delete_read_records(session_id=session_id, env=env)

    def get_server_status() -> CallToolResult:
        """サーバー自身の待ち受けのポート・プロセス ID・起動した時刻・バージョン・クローンの commit と、設定ファイルを読めるかを返却する。再起動の途中でも応答する。"""
        return admin_tools.get_server_status(env=env, control=control, clone=clone, run=run_command)

    def reload_settings(project_dir: str | None = None) -> CallToolResult:
        """設定ファイルを再読込、読めたかと読んだ値（読む索引・記録フォルダ・保持日数・project-index の接続先）を返却する。project_dir を引き渡すと、そのプロジェクトで読む索引を返却する。"""
        return admin_tools.reload_settings(project_dir=project_dir, env=env)

    async def restart_server() -> CallToolResult:
        """応答を返却した後、処理中のツールの呼び出しの終わりを待ってから待ち受けを閉じ、同じプロセスのまま再起動する。再接続してから get_server_status の started_at で確認する。"""
        return await admin_tools.restart_server(control=control)

    async def update_server() -> CallToolResult:
        """サーバーのクローンで上流の commit を fast-forward で取り込み、依存を再インストール、設定の移し替えが要らなければ再起動する。移し替えが要るときは再起動せず、手順と global-setup を返却する。"""
        return await admin_tools.update_server(
            env=env, control=control, clone=clone, run=run_command
        )

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    destructive = ToolAnnotations(destructive_hint=True, open_world_hint=False)
    # 状態の確認は再起動の途中でも応答し、再起動は begin_restart が自分で断るため、包まずに登録する
    server.add_tool(get_server_status, annotations=read_only, structured_output=False)
    server.add_tool(restart_server, annotations=destructive, structured_output=False)
    # それ以外は、再起動の途中なら断り、処理中の数を数える
    for function in (list_rules, search_rules, check_indexes, get_read_records, reload_settings):
        server.add_tool(control.guard(function), annotations=read_only, structured_output=False)
    server.add_tool(
        control.guard(write_index_entry),
        annotations=ToolAnnotations(destructive_hint=False, open_world_hint=False),
        structured_output=False,
    )
    for destructive_function in (delete_index_entry, delete_read_records, update_server):
        server.add_tool(
            control.guard(destructive_function),
            annotations=destructive,
            structured_output=False,
        )
    return server
