"""hooks/_runner.py の単体テスト。"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rule_inject.hooks._runner import log_settings_failure, run_hook
from rule_inject.shared.errors import PromptLoadError, SettingsReadError
from rule_inject.shared.logger import Component

OUTPUT = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "案内"}}


def _handle_output(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    """出力する JSON を返却する処理。"""
    return OUTPUT


def _handle_none(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """出すものが無い処理。"""
    return


def _handle_error(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """想定外の例外を送出する処理。"""
    raise RuntimeError("boom")


def _handle_prompt_error(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """プロンプトファイルを読めない処理。"""
    raise PromptLoadError("/p/a.yaml", "FileNotFoundError: 無い")


def _notice_prompt_error(message: str, log_path: Path) -> dict[str, Any]:
    """通知のプロンプトファイルを読めない通知方法。"""
    raise PromptLoadError("/p/unexpected.yaml", "FileNotFoundError: 無い")


def _notice_of_unexpected(message: str, log_path: Path) -> dict[str, Any]:
    """想定外の例外の文面とログの場所を記載した通知を作る。"""
    return {"hookSpecificOutput": {"additionalContext": f"{message} / {log_path}"}}


def test_run_hook(hook_env: dict[str, str], session_id: str) -> None:
    """処理の結果を出す（正常系）。"""
    # 準備
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_output,
        _notice_of_unexpected,
        stdin=stdin,
        stdout=stdout,
        env=hook_env,
    )
    # 検証
    assert code == 0
    assert json.loads(stdout.getvalue()) == OUTPUT


def test_run_hook_when_none(hook_env: dict[str, str], session_id: str) -> None:
    """出すものが無ければ何も出さない（正常系）。"""
    # 準備
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_none,
        _notice_of_unexpected,
        stdin=stdin,
        stdout=stdout,
        env=hook_env,
    )
    # 検証
    assert code == 0
    assert stdout.getvalue() == ""


def test_run_hook_when_unexpected(
    hook_env: dict[str, str],
    session_id: str,
    log_folder: Path,
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """想定外の例外を捕まえる（正常系）。"""
    # 準備
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_error,
        _notice_of_unexpected,
        stdin=stdin,
        stdout=stdout,
        env=hook_env,
    )
    # 検証
    assert code == 0
    logged = read_daily_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "unexpected"
    assert logged[0]["component"] == "rule_guide"
    context = json.loads(stdout.getvalue())["hookSpecificOutput"]["additionalContext"]
    assert str(log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log") in context


def test_run_hook_when_unexpected_and_settings_unreadable(
    unreadable_env: Callable[[str], dict[str, str]],
    session_id: str,
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めなくても想定外の例外を既定のログのフォルダへ書き込む（正常系）。"""
    # 準備
    env = unreadable_env("broken")
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_error,
        _notice_of_unexpected,
        stdin=stdin,
        stdout=stdout,
        env=env,
    )
    # 検証
    assert code == 0
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "unexpected"


def test_run_hook_when_prompt_unreadable(
    hook_env: dict[str, str],
    session_id: str,
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """処理のプロンプトファイルが読めなければ何も出さずにログへ書き込む（異常系）。"""
    # 準備
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    notified: list[str] = []

    def notice(message: str, log_path: Path) -> dict[str, Any]:
        notified.append(message)
        return _notice_of_unexpected(message, log_path)

    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_prompt_error,
        notice,
        stdin=stdin,
        stdout=stdout,
        env=hook_env,
    )
    # 検証
    assert code == 0
    assert stdout.getvalue() == ""
    assert notified == []
    logged = read_daily_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_prompt"
    assert logged[0]["path"] == "/p/a.yaml"


def test_run_hook_when_notice_prompt_unreadable(
    hook_env: dict[str, str],
    session_id: str,
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """想定外の例外の通知のプロンプトファイルが読めなければ何も出さない（異常系）。"""
    # 準備
    stdin = io.StringIO(json.dumps({"session_id": session_id}))
    stdout = io.StringIO()
    # 実行
    code = run_hook(
        Component("rule_guide"),
        _handle_error,
        _notice_prompt_error,
        stdin=stdin,
        stdout=stdout,
        env=hook_env,
    )
    # 検証
    assert code == 0
    assert stdout.getvalue() == ""
    operations = sorted(entry["operation"] for entry in read_daily_log())
    assert operations == ["read_prompt", "unexpected"]


def test_log_settings_failure(
    xdg_state_home: Path,
    default_log_folder: Path,
    session_id: str,
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """既定のログのフォルダへ書き込む（正常系）。"""
    # 準備
    error = SettingsReadError("/c/settings.yaml", "FileNotFoundError: 無い")
    env = {"XDG_STATE_HOME": str(xdg_state_home)}
    # 実行
    result = log_settings_failure(Component("rule_guide"), error, env, session_id)
    # 検証
    assert result == default_log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log"
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
    assert logged[0]["path"] == "/c/settings.yaml"
    assert "FileNotFoundError" in logged[0]["reason"]
