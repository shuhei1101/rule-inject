"""hooks/start_server.py の単体テスト。"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

import pytest

from rule_inject.features.guidance import build_server_start_notice
from rule_inject.features.server_start import UnitStart
from rule_inject.hooks.start_server import start_server
from rule_inject.shared.errors import UnitCheckError, UnitStartError

# パッケージ `rule_inject.hooks` は同じ名前の関数を公開するため、モジュールは import_module で取る
hook_module = importlib.import_module("rule_inject.hooks.start_server")


@pytest.fixture
def fake_server_start(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[str]]:
    """応答の確認と起動の依頼を差し替え、起動を依頼したサービス名の並びを返す factory。"""

    def _install(
        *, responds: bool = False, result: UnitStart | Exception = UnitStart.REQUESTED
    ) -> list[str]:
        """responds を応答の確認の結果にし、result を起動の依頼の戻り値（例外なら送出）にする。"""
        requested: list[str] = []

        def _responds(port: int) -> bool:
            """差し替えた応答の確認。"""
            return responds

        def _request(service: str) -> UnitStart:
            """差し替えた起動の依頼。"""
            requested.append(service)
            # 例外を渡されたときは送出し、それ以外は戻り値にする
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(hook_module, "server_responds", _responds)
        monkeypatch.setattr(hook_module, "request_unit_start", _request)
        return requested

    return _install


def test_start_server(
    settings_env: Callable[..., dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
) -> None:
    """起動を依頼したら案内を返す（正常系）。"""
    # 準備
    env = settings_env(server_service="rule-inject-ut")
    requested = fake_server_start(result=UnitStart.REQUESTED)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, env)
    # 検証
    assert output == {"additionalContext": build_server_start_notice("rule-inject-ut")}
    assert requested == ["rule-inject-ut"]


def test_start_server_when_responding(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
) -> None:
    """サーバーが応答すれば起動を依頼しない（正常系）。"""
    # 準備
    requested = fake_server_start(responds=True)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, hook_env)
    # 検証
    assert output is None
    assert requested == []


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(UnitStart.NOT_ENABLED, id="not_enabled"),
        pytest.param(UnitStart.SYSTEMCTL_MISSING, id="systemctl_missing"),
    ],
)
def test_start_server_when_not_requested(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
    result: UnitStart,
) -> None:
    """起動を依頼しなかったら何も返さない（正常系）。"""
    # 準備
    fake_server_start(result=result)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, hook_env)
    # 検証
    assert output is None
    assert read_daily_log() == []


def test_start_server_when_check_failed(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """ユニットの確認の失敗をログへ書く（正常系）。"""
    # 準備
    error = UnitCheckError("systemctl --user is-enabled rule-inject", "TimeoutExpired")
    fake_server_start(result=error)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, hook_env)
    # 検証
    assert output is None
    logs = read_daily_log()
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "check_unit"


def test_start_server_when_start_failed(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """起動の依頼の失敗をログへ書く（正常系）。"""
    # 準備
    fake_server_start(result=UnitStartError("systemctl --user start rule-inject", "終了コード 5"))
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, hook_env)
    # 検証
    assert output is None
    logs = read_daily_log()
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "start_unit"


def test_start_server_when_settings_unreadable(
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めなければ何も確かめずにログへ書く（正常系）。"""
    # 準備
    env = unreadable_env("missing")
    requested = fake_server_start(responds=False)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    output = start_server(payload, env)
    # 検証
    assert output is None
    assert requested == []
    logs = read_default_log()
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "read_settings"


def test_start_server_when_invalid_session_id(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
    fake_server_start: Callable[..., list[str]],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """session_id の形式が外れていても補助を行う（正常系）。"""
    # 準備
    fake_server_start(result=UnitStartError("systemctl --user start rule-inject", "終了コード 5"))
    payload = hook_payload("SessionStart", source="startup", session_id="../x")
    # 実行
    start_server(payload, hook_env)
    # 検証
    logs = read_daily_log()
    assert len(logs) == 1
    assert logs[0]["session_id"] is None
