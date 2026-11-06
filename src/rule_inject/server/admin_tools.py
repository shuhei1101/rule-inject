"""サーバー自身の状態の確認・設定の再読込・再起動・更新のツールの本体。"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult

from rule_inject.server._format import respond
from rule_inject.server.clone import (
    RunCommand,
    head_commit,
    plan_migrations,
    pull,
    read_version,
    sync_dependencies,
)
from rule_inject.server.control import ServerControl
from rule_inject.server.types import (
    ConfigState,
    ReloadSettingsResult,
    RestartResult,
    ServerStatusResult,
    UpdateResult,
    UpdateState,
)
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.settings import PROJECT_DIR_ENV, Settings, config_path, load_settings


def get_server_status(
    *, env: Mapping[str, str], control: ServerControl, clone: Path, run: RunCommand
) -> CallToolResult:
    """待ち受けのポート・プロセス・起動した時刻・バージョン・クローンの commit と、設定ファイルを読めるかを返す。"""
    # 設定ファイルが読めなくてもエラーにせず、読めない理由を載せる
    try:
        _read_settings(None, env)
        config = ConfigState(path=_read_config_path(env), readable=True, error=None)
    except ToolError as exc:
        config = ConfigState(path=_read_config_path(env), readable=False, error=str(exc))
    version = read_version(clone)
    commit = head_commit(clone, run=run)
    result = ServerStatusResult(
        success=True,
        output=(
            f"rule-inject {version or 'バージョン不明'}（{(commit or 'commit 不明')[:7]}）を "
            f"127.0.0.1:{control.port} で待ち受けています"
        ),
        port=control.port,
        pid=control.pid,
        started_at=control.started_at.isoformat(),
        version=version,
        clone=str(clone),
        commit=commit,
        config=config,
        restarting=control.restarting,
    )
    return respond(result, "json")


def reload_settings(*, project_dir: str | None = None, env: Mapping[str, str]) -> CallToolResult:
    """設定ファイルを読み直し、読めたかと読んだ値を返す。"""
    settings = _read_settings(project_dir, env)
    path = _read_config_path(env)
    result = ReloadSettingsResult(
        success=True,
        output=f"{path or '既定値'} を読みました（索引 {len(settings.indexes)} つ）",
        config_path=path,
        indexes=[str(index) for index in settings.indexes],
        state_dir=str(settings.state_dir),
        record_retention_days=settings.record_retention_days,
        log_retention_days=settings.log_retention_days,
        dev_docs_url=settings.dev_docs_url,
    )
    return respond(result, "json")


async def restart_server(*, control: ServerControl) -> CallToolResult:
    """再起動を始める。停止は、この応答を返し終えた後に control が作ったタスクが進める。"""
    control.begin_restart()
    result = RestartResult(
        success=True,
        output="再起動を始めました。接続し直してから get_server_status で確かめてください",
        pid=control.pid,
        restarting=True,
    )
    return respond(result, "json")


async def update_server(
    *, env: Mapping[str, str], control: ServerControl, clone: Path, run: RunCommand
) -> CallToolResult:
    """クローンへ上流の commit を取り込み、依存を入れ直し、移し替えが要らなければ再起動を始める。"""
    control.begin_update()
    try:
        # git・uv はブロックするため、スレッドで動かしてイベントループを止めない
        outcome = await asyncio.to_thread(pull, clone, run=run)
        # 取り込む commit が無い: 何も変えずに返す
        if not outcome.pulled:
            return _update_result(
                "up_to_date", outcome.before, outcome.after, [], "最新のため何も変えませんでした"
            )
        await asyncio.to_thread(sync_dependencies, clone, env, run=run)
        migrations = await asyncio.to_thread(plan_migrations, clone, env, run=run)
        # 移し替えが要る: 再起動せず、手順と global-setup を案内する
        if migrations:
            return _update_result(
                "migration_required",
                outcome.before,
                outcome.after,
                migrations,
                f"{outcome.before[:7]} から {outcome.after[:7]} へ取り込みましたが、"
                "設定の移し替えが要るため再起動していません。"
                "/rule-inject:global-setup で移し替えてから restart_server を呼んでください",
            )
        # 移し替えが要らない: 更新の印を下ろすのと再起動の開始を 1 回で行う
        control.finish_update_and_restart()
        return _update_result(
            "restarting",
            outcome.before,
            outcome.after,
            [],
            f"{outcome.before[:7]} から {outcome.after[:7]} へ更新し、再起動を始めました",
        )
    finally:
        control.end_update()


def _update_result(
    state: UpdateState, before: str, after: str, steps: list[str], output: str
) -> CallToolResult:
    """更新の応答を作る。"""
    result = UpdateResult(
        success=True, output=output, state=state, before=before, after=after, steps=steps
    )
    return respond(result, "json")


def _read_settings(project_dir: str | None, env: Mapping[str, str]) -> Settings:
    """フックと同じ規則で設定を読む。project_dir があればそのプロジェクトとして読む。"""
    if project_dir is not None and not os.path.isabs(project_dir):
        raise ToolError(f"project_dir は絶対パスで渡してください: {project_dir}")
    values = {key: value for key, value in env.items() if key != PROJECT_DIR_ENV}
    if project_dir is not None:
        values[PROJECT_DIR_ENV] = project_dir
    try:
        return load_settings(values)
    except SettingsReadError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc


def _read_config_path(env: Mapping[str, str]) -> str | None:
    """読んだ設定ファイルの場所。既定のパスにファイルが無く読まなかったときは None。"""
    path = config_path(env)
    return str(path) if path.is_file() else None
