"""インターフェース定義『設定の移し替え』の結合テスト。"""

from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

TIMEOUT_SEC = 30
OLD_SETTINGS = "# 端末の設定\nglobal:\n  server_port: 9000\n"


@pytest.fixture
def settings_file(tmp_path: Path) -> Path:
    """設定ファイルの場所（既定のパス）。"""
    return tmp_path / "xdg_config" / "rule-inject" / "settings.yaml"


@pytest.fixture
def run_migrate(tmp_path: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """`python -m rule_inject.migrate` を、既定のパスを一時フォルダへ向けて子プロセスで実行する関数。"""

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        """引数を渡して実行し、結果を返す。"""
        env = {
            name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")
        }
        env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg_config")
        return subprocess.run(
            [sys.executable, "-m", "rule_inject.migrate", *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            check=False,
        )

    return _run


def _write(path: Path, text: str) -> None:
    """設定ファイルを配置する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_normal(
    settings_file: Path,
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """古い設定ファイルの手順を示す（正常系）。"""
    # 準備
    _write(settings_file, OLD_SETTINGS)
    # 実行
    completed = run_migrate("--plan")
    # 検証
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["steps"]
    assert settings_file.read_text(encoding="utf-8") == OLD_SETTINGS


def test_normal_when_applied(
    settings_file: Path,
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """バックアップを作成して設定ファイルを書き換え、`env` へ移す値を返却する（正常系）。"""
    # 準備
    _write(settings_file, OLD_SETTINGS)
    # 実行
    completed = run_migrate()
    # 検証
    result = json.loads(completed.stdout)
    written = settings_file.read_text(encoding="utf-8")
    assert completed.returncode == 0
    assert "server_port" not in written
    assert "version:" in written
    assert "# 端末の設定" in written
    assert result["env"] == {"RULE_INJECT_PORT": "9000"}
    assert Path(result["backup"]).read_text(encoding="utf-8") == OLD_SETTINGS


def test_normal_when_current(
    settings_file: Path,
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """手順が無ければ空の手順を返却する（正常系）。"""
    # 準備
    text = f"version: {importlib.metadata.version('rule-inject')}\nglobal:\n  log_dir: /a\n"
    _write(settings_file, text)
    # 実行
    completed = run_migrate()
    # 検証
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["steps"] == []
    assert settings_file.read_text(encoding="utf-8") == text


def test_normal_when_missing(
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """設定ファイルが無ければ空の手順を返却する（正常系）。"""
    # 実行
    completed = run_migrate()
    # 検証
    assert completed.returncode == 0
    assert json.loads(completed.stdout)["steps"] == []


def test_error_when_settings_newer(
    settings_file: Path,
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """書き換えずに両方のバージョンを出力して終わる（異常系）。"""
    # 準備
    text = "version: 99.0.0\n"
    _write(settings_file, text)
    # 実行
    completed = run_migrate()
    # 検証
    assert completed.returncode == 6
    assert "99.0.0" in completed.stderr
    assert importlib.metadata.version("rule-inject") in completed.stderr
    assert settings_file.read_text(encoding="utf-8") == text


def test_error_when_unreadable(
    settings_file: Path,
    run_migrate: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """書き換えずに場所と理由を出力して終わる（異常系）。"""
    # 準備
    _write(settings_file, "global: [\n")
    # 実行
    completed = run_migrate()
    # 検証
    assert completed.returncode == 1
    assert str(settings_file) in completed.stderr
