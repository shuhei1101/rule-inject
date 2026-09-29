"""フックの標準入出力・想定外の例外・ログの共通処理。"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TextIO

from rule_inject.features.record.service import is_valid_session_id
from rule_inject.shared.errors import describe
from rule_inject.shared.logger import LOG_FILE_NAME, Component, LogOperation, write_log
from rule_inject.shared.paths import state_dir

# 入力の JSON と環境変数を受け、標準出力へ返す JSON（無ければ None）を返す
type HookHandler = Callable[[dict[str, Any], Mapping[str, str]], dict[str, Any] | None]
# 想定外の例外の文面とログの場所から、知らせの JSON（無ければ None）を作る
type UnexpectedNotifier = Callable[[str, Path], dict[str, Any] | None]


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
        # 想定外の例外はログに書き、知らせの文面を返す
        folder = state_dir(env)
        reason = describe(exc)
        write_log(
            folder,
            component=component,
            operation=LogOperation.UNEXPECTED,
            reason=reason,
            session_id=session_id,
        )
        output = on_unexpected(reason, folder / LOG_FILE_NAME)
    if output is not None:
        stdout.write(json.dumps(output) + "\n")
    return 0
