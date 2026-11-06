"""単一ユースケース「落ちていたMCPサーバーがセッションの開始時に起動される」の E2E テスト。"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

PROJECT_ROOT = Path(__file__).parents[3]
HOST = "127.0.0.1"
SERVICE_PREFIX = "rule-inject-e2e-"
UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
# 起動の案内の文面の一部（features/guidance の SERVER_START_NOTICE）
NOTICE_SNIPPET = "/mcp で rule-inject に接続し直す"
# 待ち受けの開始を待つ上限（シナリオの期待値。PoC 検証の最大 26.0 秒に余裕 50% を加えて切り上げた値）
LISTEN_TIMEOUT_SEC = 40
# サーバーの起動を待つ上限（テスト実行方法の「起動を待つ上限」）
START_TIMEOUT_SEC = 51
POLL_INTERVAL_SEC = 0.5
PROMPT = "ツールは呼ばずに、「了解」とだけ答えてください。"


@dataclass(frozen=True, slots=True)
class ServerUnit:
    """テストが配置したサーバーのユニット。"""

    service: str
    port: int
    unit_file: Path


def _free_port() -> int:
    """ポート 0 で取って閉じた、空いているポートを返す。"""
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def _listening(port: int) -> bool:
    """ポートで待ち受けているかを返す。"""
    with socket.socket() as probe:
        return probe.connect_ex((HOST, port)) == 0


def _wait_listening(port: int, limit_sec: float) -> bool:
    """limit_sec 秒以内にポートが待ち受けを始めたかを返す。"""
    deadline = time.monotonic() + limit_sec
    while time.monotonic() < deadline:
        if _listening(port):
            return True
        time.sleep(POLL_INTERVAL_SEC)
    return False


def _systemctl(*args: str) -> str:
    """`systemctl --user` を実行し、標準出力を返す。"""
    completed = subprocess.run(
        ["systemctl", "--user", *args], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip()


@pytest.fixture
def server_unit(tmp_path: Path, configure_env: Callable[..., None]) -> Iterator[ServerUnit]:
    """一意のサービス名を記載した設定ファイルと、クローンからサーバーを起動するユニットを用意する（起動も有効化もしない）。"""
    service = f"{SERVICE_PREFIX}{uuid4().hex[:8]}"
    port = _free_port()
    config = tmp_path / "config" / "settings.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "global:\n"
        f'  state_dir: "{tmp_path / "state"}"\n'
        f'  log_dir: "{tmp_path / "logs"}"\n'
        f'  server_service: "{service}"\n',
        encoding="utf-8",
    )
    configure_env({"RULE_INJECT_CONFIG": str(config), "RULE_INJECT_PORT": str(port)})
    unit_file = UNIT_DIR / f"{service}.service"
    unit = ServerUnit(service=service, port=port, unit_file=unit_file)
    yield unit
    # ユニットを止めて削除する（置いていないときの失敗は無視する）
    _systemctl("disable", "--now", service)
    unit_file.unlink(missing_ok=True)
    _systemctl("daemon-reload")


@pytest.fixture
def place_unit(tmp_path: Path) -> Callable[[ServerUnit], None]:
    """サーバーのユニットを `~/.config/systemd/user/` に配置する関数。"""

    def _place(unit: ServerUnit) -> None:
        """クローンから `RULE_INJECT_PORT` で起動するユニットを書き、systemd に読み直させる。"""
        unit.unit_file.parent.mkdir(parents=True, exist_ok=True)
        unit.unit_file.write_text(
            "[Unit]\n"
            f"Description=rule-inject MCP server ({unit.service})\n"
            "\n"
            "[Service]\n"
            f"WorkingDirectory={PROJECT_ROOT}\n"
            f"ExecStart={sys.executable} -m rule_inject.server\n"
            f"Environment=RULE_INJECT_PORT={unit.port}\n"
            f"Environment=RULE_INJECT_CONFIG={tmp_path / 'config' / 'settings.yaml'}\n"
            "SuccessExitStatus=143\n"
            "\n"
            "[Install]\n"
            "WantedBy=default.target\n",
            encoding="utf-8",
        )
        _systemctl("daemon-reload")

    return _place


@pytest.fixture
def start_server_logs(tmp_path: Path) -> Callable[[], list[dict[str, Any]]]:
    """ログのフォルダのログのうち、`component: start_server` の行を返す関数。"""

    def _read() -> list[dict[str, Any]]:
        """`{log_dir}/*_rule-inject.log` の各行を読み、サーバーの起動の補助の行だけを返す。"""
        lines = [
            json.loads(line)
            for log in sorted((tmp_path / "logs").glob("*_rule-inject.log"))
            for line in log.read_text(encoding="utf-8").splitlines()
        ]
        return [line for line in lines if line.get("component") == "start_server"]

    return _read


def test_normal(
    server_unit: ServerUnit,
    place_unit: Callable[[ServerUnit], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """応答しないサーバーを、セッションの開始時にユニットで起動し、`/mcp` で接続し直す案内を載せる（正常シナリオ）。"""
    # 準備
    place_unit(server_unit)
    _systemctl("enable", server_unit.service)
    # 実行
    run = run_claude(PROMPT, max_turns=1)
    # 検証
    assert NOTICE_SNIPPET in transcript_text(run.session_id)
    assert _wait_listening(server_unit.port, LISTEN_TIMEOUT_SEC)
    assert _systemctl("is-active", server_unit.service) == "active"


def test_normal_when_server_responding(
    server_unit: ServerUnit,
    place_unit: Callable[[ServerUnit], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """サーバーが応答すれば、起動を依頼せず案内も載せない（正常シナリオ（サーバーが応答する））。"""
    # 準備
    place_unit(server_unit)
    _systemctl("enable", "--now", server_unit.service)
    assert _wait_listening(server_unit.port, START_TIMEOUT_SEC)
    started = _systemctl("show", "-p", "ActiveEnterTimestampMonotonic", server_unit.service)
    # 実行
    run = run_claude(PROMPT, max_turns=1)
    # 検証
    assert NOTICE_SNIPPET not in transcript_text(run.session_id)
    after = _systemctl("show", "-p", "ActiveEnterTimestampMonotonic", server_unit.service)
    assert after == started


def test_normal_when_unit_disabled(
    server_unit: ServerUnit,
    place_unit: Callable[[ServerUnit], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
    start_server_logs: Callable[[], list[dict[str, Any]]],
) -> None:
    """ユニットが有効でなければ起動しない（正常シナリオ（ユニットが有効でない））。"""
    # 準備
    place_unit(server_unit)
    # 実行
    run = run_claude(PROMPT, max_turns=1)
    # 検証
    assert NOTICE_SNIPPET not in transcript_text(run.session_id)
    assert _systemctl("is-active", server_unit.service) == "inactive"
    assert start_server_logs() == []


def test_normal_when_no_unit(
    server_unit: ServerUnit,
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
    start_server_logs: Callable[[], list[dict[str, Any]]],
) -> None:
    """ユニットが無ければ何もせず、セッションが回答を返して終わる（正常シナリオ（ユニットが無い））。"""
    # 実行
    run = run_claude(PROMPT, max_turns=1)
    # 検証
    assert NOTICE_SNIPPET not in transcript_text(run.session_id)
    assert run.result["type"] == "result"
    assert start_server_logs() == []
