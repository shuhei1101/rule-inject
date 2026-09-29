"""shared/paths.py の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from rule_inject.shared import paths


def test_state_dir_when_env_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """環境変数の値を使う（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path))
    # 実行
    result = paths.state_dir({"RULE_INJECT_STATE_DIR": "~/x"})
    # 検証
    assert result == tmp_path / "x"


def test_state_dir_when_xdg_state_home() -> None:
    """XDG_STATE_HOME の下を使う（正常系）。"""
    # 実行
    result = paths.state_dir({"XDG_STATE_HOME": "/s"})
    # 検証
    assert result == Path("/s/rule-inject")


def test_state_dir_when_no_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """既定の場所を使う（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path))
    # 実行
    result = paths.state_dir({})
    # 検証
    assert result == tmp_path / ".local" / "state" / "rule-inject"


def test_resolve_location_when_url() -> None:
    """URL は変えない（正常系）。"""
    # 実行
    result = paths.resolve_location("https://example.com/a.md", Path("/p"))
    # 検証
    assert result == "https://example.com/a.md"


def test_resolve_location_when_relative() -> None:
    """相対パスを基準から解く（正常系）。"""
    # 実行
    result = paths.resolve_location("../r/a.md", Path("/p/idx"))
    # 検証
    assert result == "/p/r/a.md"


def test_resolve_location_when_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`~` を展開する（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path))
    # 実行
    result = paths.resolve_location("~/r/a.md", Path("/p"))
    # 検証
    assert result == str(tmp_path / "r" / "a.md")


def test_log_dir_when_env_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """環境変数の値を使う（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path))
    # 実行
    result = paths.log_dir({"RULE_INJECT_LOG_DIR": "~/x"})
    # 検証
    assert result == tmp_path / "x"


def test_log_dir_when_xdg_state_home() -> None:
    """XDG_STATE_HOME の下を使う（正常系）。"""
    # 実行
    result = paths.log_dir({"XDG_STATE_HOME": "/s", "RULE_INJECT_STATE_DIR": "/r"})
    # 検証
    assert result == Path("/s/rule-inject/logs")


def test_log_dir_when_no_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """既定の場所を使う（正常系）。"""
    # 準備
    monkeypatch.setenv("HOME", str(tmp_path))
    # 実行
    result = paths.log_dir({})
    # 検証
    assert result == tmp_path / ".local" / "state" / "rule-inject" / "logs"
