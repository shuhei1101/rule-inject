"""フックの標準入出力・想定外の例外・ログの共通処理。"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from rule_inject.features.guidance import build_failure_notice
from rule_inject.features.record.service import is_valid_session_id
from rule_inject.shared.errors import SettingsReadError, describe
from rule_inject.shared.logger import Component, LogOperation, log_file_path, write_log
from rule_inject.shared.paths import default_log_dir
from rule_inject.shared.settings import load_settings

# 設定ファイルを読めなかったときに `build_failure_notice` へ渡す 1 文
SETTINGS_FAILURE_SUMMARY = "設定ファイルを読めませんでした"

# 入力の JSON と環境変数を受け、標準出力へ返す JSON（無ければ None）を返す
type HookHandler = Callable[[dict[str, Any], Mapping[str, str]], dict[str, Any] | None]
# 想定外の例外の文面とログの場所から、知らせの JSON（無ければ None）を作る
type UnexpectedNotifier = Callable[[str, Path], dict[str, Any] | None]


def log_settings_failure(
    component: Component,
    error: SettingsReadError,
    env: Mapping[str, str],
    session_id: str | None,
) -> Path:
    """設定ファイルを読めなかったことを既定のログのフォルダへ書き、そのログのファイルの場所を返す。"""
    # 設定ファイルの `global.log_dir` は読めないため、既定のログのフォルダへ書く
    log_folder = default_log_dir(env)
    write_log(
        log_folder,
        component=component,
        operation=LogOperation.READ_SETTINGS,
        reason=error.reason,
        session_id=session_id,
        path=error.path,
    )
    return log_file_path(log_folder, datetime.now(UTC).date())


def settings_failure_notice(
    component: Component,
    error: SettingsReadError,
    env: Mapping[str, str],
    session_id: str | None,
) -> str:
    """設定ファイルを読めなかったことをログへ書き、場所と理由とログの場所を載せた知らせの文を返す。"""
    log_path = log_settings_failure(component, error, env, session_id)
    return build_failure_notice(SETTINGS_FAILURE_SUMMARY, [error], log_path)


def run_hook(
    component: Component,
    handle: HookHandler,
    on_unexpected: UnexpectedNotifier,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    env: Mapping[str, str] = os.environ,
) -> int:
    """標準入力を読んで処理を呼び、結果を標準出力へ出す。想定外の例外も捕まえて 0 を返す。"""
    session_id: str | None = None
    try:
        payload = json.load(stdin)
        session_id = (
            payload.get("session_id") if is_valid_session_id(payload.get("session_id")) else None
        )
        output = handle(payload, env)
    except Exception as exc:  # noqa: BLE001 -- フックの最上位。操作を止めないため全ての例外を捕まえる
        # 想定外の例外はログに書き、知らせの文面を返す。設定ファイルが読めなければ既定のログのフォルダへ書く
        try:
            log_folder = load_settings(env).log_dir
        except SettingsReadError:
            log_folder = default_log_dir(env)
        reason = describe(exc)
        write_log(
            log_folder,
            component=component,
            operation=LogOperation.UNEXPECTED,
            reason=reason,
            session_id=session_id,
        )
        output = on_unexpected(reason, log_file_path(log_folder, datetime.now(UTC).date()))
    if output is not None:
        stdout.write(json.dumps(output) + "\n")
    return 0
