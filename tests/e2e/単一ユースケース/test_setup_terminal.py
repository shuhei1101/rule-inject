"""単一ユースケース「端末をセットアップする」の E2E テスト。"""

from __future__ import annotations

import importlib.metadata
import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).parents[3]
LIST_RULES = "list_rules"
HOST = "127.0.0.1"
OLD_SETTINGS = "global:\n  server_port: 9000\n"
# 起動を待つ上限（テスト実行方法の「起動を待つ上限」）
START_TIMEOUT_SEC = 51
POLL_INTERVAL_SEC = 0.1


def _settings_env(path: Path) -> dict[str, str]:
    """`settings.json` の `env` を返す（ファイルが無ければ空）。"""
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("env", {}))


def _prompt(setup_env: Any, *extra: str) -> str:
    """スキルを呼ぶプロンプトを作る。"""
    args = [f"--clone {PROJECT_ROOT}", f"--service {setup_env.service}", *extra]
    return f"/rule-inject:global-setup {' '.join(args)}"


def _place(path: Path, text: str) -> None:
    """端末の設定を配置する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def resident(setup_env: Any) -> Iterator[subprocess.Popen[bytes]]:
    """`RULE_INJECT_PORT` のポートで待ち受けるサーバーを前面で起動する。"""
    process = subprocess.Popen(
        [sys.executable, "-m", "rule_inject.server"],
        cwd=PROJECT_ROOT,
        env={"PATH": "/usr/bin:/bin", **setup_env.env},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 待ち受けるまで待つ
    deadline = time.monotonic() + START_TIMEOUT_SEC
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            if probe.connect_ex((HOST, setup_env.port)) == 0:
                break
        time.sleep(POLL_INTERVAL_SEC)
    yield process
    process.terminate()
    process.wait()


def test_normal(
    setup_env: Any,
    make_index: Callable[..., Path],
    run_skill: Callable[[str], Any],
    list_tool_names: Callable[[int], list[str]],
) -> None:
    """端末の設定を雛形から作り、サーバーを起動して結果を示す（正常シナリオ）。"""
    # 準備
    index = make_index()
    # 実行
    run = run_skill(_prompt(setup_env, f"--index {index}"))
    # 検証
    written = setup_env.config_file.read_text(encoding="utf-8")
    assert f"version: {importlib.metadata.version('rule-inject')}" in written
    assert str(index) in written
    assert "RULE_INJECT_CONFIG" not in _settings_env(setup_env.claude_settings)
    assert LIST_RULES in list_tool_names(setup_env.port)
    assert str(setup_env.config_file) in run.answer


def test_normal_when_settings_old(
    setup_env: Any,
    tmp_path: Path,
    run_skill: Callable[[str], Any],
) -> None:
    """古い設定を確認の後に移し替える（正常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, OLD_SETTINGS)
    # 実行
    run_skill(_prompt(setup_env, "--yes"))
    # 検証
    written = setup_env.config_file.read_text(encoding="utf-8")
    backups = list((tmp_path / "xdg_config" / "rule-inject" / "bk").iterdir())
    assert "server_port" not in written
    assert f"version: {importlib.metadata.version('rule-inject')}" in written
    assert _settings_env(setup_env.claude_settings)["RULE_INJECT_PORT"] == "9000"
    assert backups[0].read_text(encoding="utf-8") == OLD_SETTINGS


def test_normal_when_custom_path(
    setup_env: Any,
    tmp_path: Path,
    make_index: Callable[..., Path],
    run_skill: Callable[[str], Any],
) -> None:
    """既定と違う場所に設定を作り、`env` のほかのキーを変えない（正常シナリオ）。"""
    # 準備
    custom = tmp_path / "custom" / "settings.yaml"
    index = make_index()
    setup_env.claude_settings.write_text(
        json.dumps({"env": {"OTHER_KEY": "value"}}), encoding="utf-8"
    )
    # 実行
    run_skill(_prompt(setup_env, f"--config {custom}", f"--index {index}"))
    # 検証
    env = _settings_env(setup_env.claude_settings)
    assert custom.exists()
    assert env["RULE_INJECT_CONFIG"] == str(custom)
    assert env["OTHER_KEY"] == "value"


def test_normal_when_old_registration(
    setup_env: Any,
    make_index: Callable[..., Path],
    run_claude_cli: Callable[..., subprocess.CompletedProcess[str]],
    run_skill: Callable[[str], Any],
) -> None:
    """ユーザースコープの旧い登録を確認の後に削除する（正常シナリオ）。"""
    # 準備
    url = f"http://{HOST}:{setup_env.port}/mcp"
    run_claude_cli("mcp", "add", "--transport", "http", "-s", "user", "rule-inject", url)
    # 実行
    run = run_skill(_prompt(setup_env, f"--index {make_index()}", "--yes"))
    # 検証
    listed = run_claude_cli("mcp", "get", "rule-inject")
    assert listed.returncode != 0
    assert "rule-inject" in run.answer


def test_normal_when_settings_current(
    setup_env: Any,
    resident: subprocess.Popen[bytes],
    run_skill: Callable[[str], Any],
) -> None:
    """今のバージョンの設定は書き換えず、接続だけを確認する（正常シナリオ）。"""
    # 準備
    text = f"version: {importlib.metadata.version('rule-inject')}\nglobal:\n  log_dir: /tmp/l\n"
    _place(setup_env.config_file, text)
    unit = Path.home() / ".config" / "systemd" / "user" / f"{setup_env.service}.service"
    # 実行
    run = run_skill(_prompt(setup_env))
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == text
    assert not setup_env.claude_settings.exists()
    assert not unit.exists()
    assert str(setup_env.port) in run.answer


def test_error_when_settings_newer(
    setup_env: Any,
    run_skill: Callable[[str], Any],
) -> None:
    """設定のほうが新しいときは書き換えずに止まる（異常シナリオ）。"""
    # 準備
    text = "version: 99.0.0\n"
    _place(setup_env.config_file, text)
    # 実行
    run = run_skill(_prompt(setup_env))
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == text
    assert not setup_env.claude_settings.exists()
    assert "99.0.0" in run.answer
    assert importlib.metadata.version("rule-inject") in run.answer


def test_error_when_declined(
    setup_env: Any,
    run_skill: Callable[[str], Any],
) -> None:
    """移し替えを断ると何も記載せずに止まる（異常シナリオ）。"""
    # 準備
    _place(setup_env.config_file, OLD_SETTINGS)
    unit = Path.home() / ".config" / "systemd" / "user" / f"{setup_env.service}.service"
    # 実行
    run = run_skill(_prompt(setup_env, "--no"))
    # 検証
    assert setup_env.config_file.read_text(encoding="utf-8") == OLD_SETTINGS
    assert not setup_env.claude_settings.exists()
    assert not unit.exists()
    assert "server_port" in run.answer


def test_error_when_port_in_use(
    setup_env: Any,
    make_index: Callable[..., Path],
    run_skill: Callable[[str], Any],
) -> None:
    """ポートが使われているときはログの場所と修正方法を示して止まる（異常シナリオ）。"""
    # 準備: `RULE_INJECT_PORT` のポートを MCP でないソケットで待ち受ける
    with socket.create_server((HOST, setup_env.port)):
        # 実行
        run = run_skill(_prompt(setup_env, f"--index {make_index()}"))
    # 検証
    assert str(setup_env.port) in run.answer
    assert "journalctl" in run.answer
