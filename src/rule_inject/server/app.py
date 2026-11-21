"""コンポジションルート。依存を作ってツールへ引き渡し、`MCPServer` に 11 のツールを登録する。"""

from collections.abc import Callable, Mapping
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
from rule_inject.server.prompts import load_prompt
from rule_inject.server.types import ResponseFormat
from rule_inject.shared.settings import SESSION_ENV_KEYS

# MCPServer の名前（プロンプトファイルの id の mcp/{SERVER_NAME}/... にも使用する）
SERVER_NAME = "rule-inject"
# `check_indexes` がプロジェクトのファイルを辿る時間の上限（秒）
UNMATCHED_SCAN_TIME_LIMIT = 30
# `check_indexes` が project-index への問い合わせの応答を待つ時間の上限（秒）
DEV_DOCS_TIMEOUT = 207
LIST_LIMIT_FIELD = Field(ge=1, le=tools.MAX_LIST_LIMIT)
CURSOR_FIELD = Field(pattern=tools.CURSOR_PATTERN)
POSITION_FIELD = Field(ge=0)


def _session_environment(
    env: Mapping[str, str], session_env: dict[str, str] | None
) -> Mapping[str, str]:
    """サーバーの環境変数から `SESSION_ENV_KEYS` を除き、ツールを呼んだセッションの `session_env` を重ねる。"""
    # フックを通らない呼び出しは、サーバーを起動した環境の環境変数で決める
    if session_env is None:
        return env
    # セッションに無い設定の環境変数をサーバーの値で補わないよう、3 つを除いてから重ねる（変数参照の名前も重ねる）
    base = {key: value for key, value in env.items() if key not in SESSION_ENV_KEYS}
    return {**base, **session_env}


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
    # 接続時の instructions はプロンプトファイルから読み込む（読めなければ PromptLoadError を送出する）
    server = MCPServer(
        SERVER_NAME, instructions=load_prompt(clone, f"mcp/{SERVER_NAME}/instructions")
    )

    def describe(function: Callable[..., Any]) -> str:
        """ツールの description を、ツールの名前の _ を - にしたプロンプトファイルから読み込む。"""
        return load_prompt(clone, f"mcp/{SERVER_NAME}/tools/{function.__name__.replace('_', '-')}")

    # 依存（env・validator・locks・scan_time_limit・dev_docs_timeout・control・clone・run_command）を閉じ込め、引数をツールの引数だけにした関数を登録する
    # （partial で引き渡すと、依存の引数がツールの引数の Schema に残るため）
    def list_rules(
        project_dir: str,
        limit: Annotated[int, LIST_LIMIT_FIELD] = tools.DEFAULT_LIST_LIMIT,
        cursor: Annotated[str | None, CURSOR_FIELD] = None,
        format: ResponseFormat = "markdown",
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        return tools.list_rules(
            project_dir=project_dir,
            limit=limit,
            cursor=cursor,
            format=format,
            env=_session_environment(env, session_env),
        )

    def search_rules(
        project_dir: str,
        path: str | None = None,
        operation: Literal["read", "write"] | None = None,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        format: ResponseFormat = "markdown",
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        return tools.search_rules(
            project_dir=project_dir,
            path=path,
            operation=operation,
            tool_name=tool_name,
            arguments=arguments,
            format=format,
            env=_session_environment(env, session_env),
        )

    async def check_indexes(
        project_dir: str,
        format: ResponseFormat = "markdown",
        include_global: bool = False,
        cursor: str | None = None,
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        return await check_tools.check_indexes(
            project_dir=project_dir,
            format=format,
            include_global=include_global,
            cursor=cursor,
            env=_session_environment(env, session_env),
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
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        session = _session_environment(env, session_env)
        return tools.write_index_entry(
            project_dir=project_dir,
            index=index,
            entry=entry,
            position=position,
            expected_rev=expected_rev,
            remove_keys=remove_keys,
            dry_run=dry_run,
            env=session,
            locks=locks,
            check_change=partial(check_change, env=session, validator=validator),
        )

    def delete_index_entry(
        project_dir: str,
        index: str,
        position: Annotated[int, POSITION_FIELD],
        expected_rev: str,
        dry_run: bool = False,
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        return tools.delete_index_entry(
            project_dir=project_dir,
            index=index,
            position=position,
            expected_rev=expected_rev,
            dry_run=dry_run,
            env=_session_environment(env, session_env),
            locks=locks,
        )

    def get_read_records(
        session_id: str | None = None,
        limit: Annotated[int, LIST_LIMIT_FIELD] = tools.DEFAULT_LIST_LIMIT,
        cursor: Annotated[str | None, CURSOR_FIELD] = None,
        format: ResponseFormat = "markdown",
        session_env: dict[str, str] | None = None,
    ) -> CallToolResult:
        return record_tools.get_read_records(
            session_id=session_id,
            limit=limit,
            cursor=cursor,
            format=format,
            env=_session_environment(env, session_env),
        )

    def delete_read_records(
        session_id: str, session_env: dict[str, str] | None = None
    ) -> CallToolResult:
        return record_tools.delete_read_records(
            session_id=session_id, env=_session_environment(env, session_env)
        )

    def get_server_status() -> CallToolResult:
        return admin_tools.get_server_status(env=env, control=control, clone=clone, run=run_command)

    def reload_settings(project_dir: str | None = None) -> CallToolResult:
        return admin_tools.reload_settings(project_dir=project_dir, env=env)

    async def restart_server() -> CallToolResult:
        return await admin_tools.restart_server(control=control)

    async def update_server() -> CallToolResult:
        return await admin_tools.update_server(
            env=env, control=control, clone=clone, run=run_command
        )

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    # 再起動はプロセスを入れ替えるが、設定や記録を失わせないため破壊的にしない
    restartable = ToolAnnotations(destructive_hint=False, open_world_hint=False)
    destructive = ToolAnnotations(destructive_hint=True, open_world_hint=False)
    # 状態の確認は再起動の途中でも応答し、再起動は begin_restart が自分で断るため、包まずに登録する
    server.add_tool(
        get_server_status,
        description=describe(get_server_status),
        annotations=read_only,
        structured_output=False,
    )
    server.add_tool(
        restart_server,
        description=describe(restart_server),
        annotations=restartable,
        structured_output=False,
    )
    # それ以外は、再起動の途中なら断り、処理中の数を数える
    for function in (list_rules, search_rules, check_indexes, get_read_records, reload_settings):
        server.add_tool(
            control.guard(function),
            description=describe(function),
            annotations=read_only,
            structured_output=False,
        )
    # 索引のエントリの書き換え・削除、記録の削除、クローンの更新は破壊的にする
    for destructive_function in (
        write_index_entry,
        delete_index_entry,
        delete_read_records,
        update_server,
    ):
        server.add_tool(
            control.guard(destructive_function),
            description=describe(destructive_function),
            annotations=destructive,
            structured_output=False,
        )
    return server
