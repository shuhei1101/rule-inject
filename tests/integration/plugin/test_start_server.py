"""サーバーの起動の補助（SessionStart フック）の結合テスト。"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

SERVICE = "rule-inject-it"

# 受け取った引数を 1 行ずつ追記し、環境変数で決めた終了コードを返す systemctl の代わり
FAKE_SYSTEMCTL = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_SYSTEMCTL_CALLS"
case "$2" in
  is-enabled)
    sleep "${FAKE_IS_ENABLED_SLEEP:-0}"
    exit "${FAKE_IS_ENABLED_EXIT:-0}"
    ;;
  start)
    exit "${FAKE_START_EXIT:-0}"
    ;;
esac
exit 0
"""


@pytest.fixture
def closed_port() -> int:
    """空いているポートを取って閉じた、どのプロセスも待ち受けていないポート。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def listening_port() -> Iterator[int]:
    """127.0.0.1 の空いているポートで待ち受け、そのポートを返す。"""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        yield listener.getsockname()[1]


@pytest.fixture
def fake_systemctl(tmp_path: Path) -> Callable[..., dict[str, str]]:
    """`PATH` の先頭に systemctl の代わりを置き、フックに渡す環境変数を返す factory。"""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    script = bin_dir / "systemctl"
    script.write_text(FAKE_SYSTEMCTL, encoding="utf-8")
    script.chmod(0o755)

    def _env(port: int, **outcome: str) -> dict[str, str]:
        """port を `RULE_INJECT_PORT` にし、outcome（`FAKE_*` の値）を環境変数に加える。"""
        return {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RULE_INJECT_PORT": str(port),
            "FAKE_SYSTEMCTL_CALLS": str(tmp_path / "systemctl-calls.txt"),
            **outcome,
        }

    return _env


@pytest.fixture
def systemctl_calls(tmp_path: Path) -> Callable[[], list[str]]:
    """systemctl の代わりが受け取った引数を、呼ばれた順に返す関数。"""

    def _read() -> list[str]:
        """記録のファイルを読む（無ければ空）。"""
        calls = tmp_path / "systemctl-calls.txt"
        return calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []

    return _read


@pytest.fixture
def today_logs() -> Callable[[Path], list[dict[str, Any]]]:
    """ログのフォルダの今日（UTC）のログを、1 行ごとの dict で返す関数。"""

    def _read(folder: Path) -> list[dict[str, Any]]:
        """`{folder}/{yyyymmdd}_rule-inject.log` を読む（無ければ空）。"""
        log = folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log"
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return [json.loads(line) for line in lines]

    return _read


def test_normal(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    systemctl_calls: Callable[[], list[str]],
    closed_port: int,
) -> None:
    """サーバーが応答せずユニットが有効なとき、起動を依頼して `/mcp` で接続し直す案内を返す（正常系）。"""
    # 準備
    env = fake_systemctl(closed_port)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert systemctl_calls() == [
        f"--user is-enabled --quiet -- {SERVICE}",
        f"--user start --no-block -- {SERVICE}",
    ]
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert SERVICE in output["additionalContext"]
    assert "/mcp" in output["additionalContext"]
    assert completed.returncode == 0


def test_normal_when_server_responding(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    systemctl_calls: Callable[[], list[str]],
    listening_port: int,
) -> None:
    """ポートへ接続できたら、systemctl を呼ばずに何も返さない（正常系）。"""
    # 準備
    env = fake_systemctl(listening_port)
    payload = hook_payload("SessionStart", source="resume")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert systemctl_calls() == []
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_unit_disabled(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    systemctl_calls: Callable[[], list[str]],
    today_logs: Callable[[Path], list[dict[str, Any]]],
    log_folder: Path,
    closed_port: int,
) -> None:
    """ユニットが有効でない・無いときは、起動を依頼せず何も返さない（正常系）。"""
    # 準備
    env = fake_systemctl(closed_port, FAKE_IS_ENABLED_EXIT="1")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert systemctl_calls() == [f"--user is-enabled --quiet -- {SERVICE}"]
    assert completed.stdout == ""
    assert today_logs(log_folder) == []
    assert completed.returncode == 0


def test_normal_when_systemctl_missing(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    today_logs: Callable[[Path], list[dict[str, Any]]],
    log_folder: Path,
    tmp_path: Path,
    closed_port: int,
) -> None:
    """`systemctl` が `PATH` に無い端末では、起動を依頼せず何も返さない（正常系）。"""
    # 準備
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = {"PATH": str(empty_bin), "RULE_INJECT_PORT": str(closed_port)}
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert completed.stdout == ""
    assert today_logs(log_folder) == []
    assert completed.returncode == 0


def test_error_when_start_failed(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    today_logs: Callable[[Path], list[dict[str, Any]]],
    log_folder: Path,
    closed_port: int,
) -> None:
    """`start --no-block` が 0 以外で終わったら、案内を返さずログへ記載する（異常系）。"""
    # 準備
    env = fake_systemctl(closed_port, FAKE_START_EXIT="5")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert completed.stdout == ""
    logs = today_logs(log_folder)
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "start_unit"
    assert "5" in logs[0]["reason"]
    assert completed.returncode == 0


def test_error_when_systemctl_timed_out(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    systemctl_calls: Callable[[], list[str]],
    today_logs: Callable[[Path], list[dict[str, Any]]],
    log_folder: Path,
    closed_port: int,
) -> None:
    """`is-enabled` が非機能要件の待ちを過ぎたら打ち切り、起動を依頼せずログへ記載する（異常系）。"""
    # 準備
    env = fake_systemctl(closed_port, FAKE_IS_ENABLED_SLEEP="2")
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": SERVICE}, extra_env=env
    )
    # 検証
    assert systemctl_calls() == [f"--user is-enabled --quiet -- {SERVICE}"]
    assert completed.stdout == ""
    logs = today_logs(log_folder)
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "check_unit"
    assert completed.returncode == 0


def test_error_when_settings_unreadable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
    fake_systemctl: Callable[..., dict[str, str]],
    systemctl_calls: Callable[[], list[str]],
    today_logs: Callable[[Path], list[dict[str, Any]]],
    default_log_folder: Path,
    closed_port: int,
) -> None:
    """設定ファイルが読めないときは、応答も確かめずに何もせず、既定のログのフォルダへ記載する（異常系）。"""
    # 準備
    env = fake_systemctl(closed_port)
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = run_hook(
        "start_server", payload, global_values={"server_service": "a b"}, extra_env=env
    )
    # 検証
    assert systemctl_calls() == []
    assert completed.stdout == ""
    logs = today_logs(default_log_folder)
    assert len(logs) == 1
    assert logs[0]["component"] == "start_server"
    assert logs[0]["operation"] == "read_settings"
    assert completed.returncode == 0
