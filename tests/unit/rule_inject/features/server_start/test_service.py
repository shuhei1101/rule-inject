"""features/server_start/service.py の単体テスト。"""

from __future__ import annotations

import socket
import subprocess
from collections.abc import Callable, Iterator, Sequence
from typing import Any

import pytest

from rule_inject.features.server_start import service
from rule_inject.features.server_start.service import (
    PROBE_TIMEOUT_SECONDS,
    SYSTEMCTL_TIMEOUT_SECONDS,
    request_unit_start,
    server_responds,
)
from rule_inject.features.server_start.types import UnitStart
from rule_inject.shared.errors import UnitCheckError, UnitStartError

IS_ENABLED = ["systemctl", "--user", "is-enabled", "--quiet", "--", "rule-inject"]
START = ["systemctl", "--user", "start", "--no-block", "--", "rule-inject"]


@pytest.fixture
def listening_port() -> Iterator[int]:
    """127.0.0.1 の空いているポートで待ち受け、そのポートを返す。"""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        yield listener.getsockname()[1]


@pytest.fixture
def closed_port() -> int:
    """空いているポートを取って閉じた、どのプロセスも待ち受けていないポート。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def fake_systemctl(monkeypatch: pytest.MonkeyPatch) -> Callable[..., list[dict[str, Any]]]:
    """subprocess.run を差し替え、受け取った引数と timeout の並びを返す factory。"""

    def _install(
        *, is_enabled: int | Exception = 0, start: int | Exception = 0
    ) -> list[dict[str, Any]]:
        """is-enabled・start の終了コード（例外なら送出）を決める。"""
        calls: list[dict[str, Any]] = []

        def _run(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
            """差し替えた subprocess.run。"""
            calls.append({"args": list(args), "timeout": kwargs.get("timeout")})
            # is-enabled と start のどちらの呼び出しかで応答を選ぶ
            outcome = is_enabled if "is-enabled" in args else start
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(list(args), outcome)

        monkeypatch.setattr(service.subprocess, "run", _run)
        return calls

    return _install


def test_server_responds(listening_port: int) -> None:
    """待ち受けているポートなら真（正常系）。"""
    # 実行
    result = server_responds(listening_port)
    # 検証
    assert result is True


def test_server_responds_when_refused(closed_port: int) -> None:
    """待ち受けていないポートなら偽（正常系）。"""
    # 実行
    result = server_responds(closed_port)
    # 検証
    assert result is False


def test_server_responds_when_timed_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """待ちを過ぎたら偽（正常系）。"""
    # 準備
    timeouts: list[float] = []

    def _connect(address: tuple[str, int], timeout: float) -> socket.socket:
        """待ちを過ぎた接続。"""
        timeouts.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.setattr(service.socket, "create_connection", _connect)
    # 実行
    result = server_responds(8783)
    # 検証
    assert result is False
    assert timeouts == [PROBE_TIMEOUT_SECONDS]


def test_request_unit_start(fake_systemctl: Callable[..., list[dict[str, Any]]]) -> None:
    """有効なユニットへ起動を依頼する（正常系）。"""
    # 準備
    calls = fake_systemctl(is_enabled=0, start=0)
    # 実行
    result = request_unit_start("rule-inject")
    # 検証
    assert result is UnitStart.REQUESTED
    assert calls == [
        {"args": IS_ENABLED, "timeout": SYSTEMCTL_TIMEOUT_SECONDS},
        {"args": START, "timeout": SYSTEMCTL_TIMEOUT_SECONDS},
    ]


def test_request_unit_start_when_not_enabled(
    fake_systemctl: Callable[..., list[dict[str, Any]]],
) -> None:
    """有効でなければ起動を依頼しない（正常系）。"""
    # 準備
    calls = fake_systemctl(is_enabled=1)
    # 実行
    result = request_unit_start("rule-inject")
    # 検証
    assert result is UnitStart.NOT_ENABLED
    assert calls == [{"args": IS_ENABLED, "timeout": SYSTEMCTL_TIMEOUT_SECONDS}]


def test_request_unit_start_when_systemctl_missing(
    fake_systemctl: Callable[..., list[dict[str, Any]]],
) -> None:
    """systemctl が無ければ何もしない（正常系）。"""
    # 準備
    fake_systemctl(is_enabled=FileNotFoundError("systemctl"))
    # 実行
    result = request_unit_start("rule-inject")
    # 検証
    assert result is UnitStart.SYSTEMCTL_MISSING


def test_request_unit_start_when_check_timed_out(
    fake_systemctl: Callable[..., list[dict[str, Any]]],
) -> None:
    """is-enabled の打ち切り（異常系）。"""
    # 準備
    calls = fake_systemctl(is_enabled=subprocess.TimeoutExpired(IS_ENABLED, 0.3))
    # 実行・検証
    with pytest.raises(UnitCheckError, match="is-enabled"):
        request_unit_start("rule-inject")
    assert calls == [{"args": IS_ENABLED, "timeout": SYSTEMCTL_TIMEOUT_SECONDS}]


def test_request_unit_start_when_start_timed_out(
    fake_systemctl: Callable[..., list[dict[str, Any]]],
) -> None:
    """start の打ち切り（異常系）。"""
    # 準備
    fake_systemctl(is_enabled=0, start=subprocess.TimeoutExpired(START, 0.3))
    # 実行・検証
    with pytest.raises(UnitStartError, match="start"):
        request_unit_start("rule-inject")


def test_request_unit_start_when_start_failed(
    fake_systemctl: Callable[..., list[dict[str, Any]]],
) -> None:
    """start の失敗（異常系）。"""
    # 準備
    fake_systemctl(is_enabled=0, start=5)
    # 実行・検証
    with pytest.raises(UnitStartError, match="終了コード 5"):
        request_unit_start("rule-inject")
