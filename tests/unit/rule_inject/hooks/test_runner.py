"""hooks/_runner.py の単体テスト。"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from rule_inject.hooks._runner import run_hook
from rule_inject.shared.logger import Component

OUTPUT = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "案内"}}


def _handle_output(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    """出力する JSON を返す処理。"""
    return OUTPUT


def _handle_none(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """出すものが無い処理。"""
    return


def _handle_error(payload: dict[str, Any], env: Mapping[str, str]) -> None:
    """想定外の例外を送出する処理。"""
    raise RuntimeError("boom")


def _notice_of_unexpected(message: str, log_path: Path) -> dict[str, Any]:
    """想定外の例外の文面とログの場所を載せた知らせを作る。"""
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
    state_dir: Path,
    read_log: Callable[[], list[dict[str, Any]]],
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
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "unexpected"
    assert logged[0]["component"] == "rule_guide"
    context = json.loads(stdout.getvalue())["hookSpecificOutput"]["additionalContext"]
    assert str(state_dir / "rule-inject.log") in context
