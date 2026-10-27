"""shared/paths.py の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from rule_inject.shared import paths


def test_resolve_location_when_relative() -> None:
    """相対パスを基準から解く（正常系）。"""
    # 実行
    result = paths.resolve_location("../r/a.md", Path("/p/idx"))
    # 検証
    assert result == "/p/r/a.md"


def test_resolve_location_when_home(isolated_home: Path) -> None:
    """`~` を展開する（正常系）。"""
    # 実行
    result = paths.resolve_location("~/r/a.md", Path("/p"))
    # 検証
    assert result == str(isolated_home / "r" / "a.md")


def test_default_state_dir_when_xdg_state_home() -> None:
    """XDG_STATE_HOME の下を使う（正常系）。"""
    # 実行
    result = paths.default_state_dir({"XDG_STATE_HOME": "/s"})
    # 検証
    assert result == Path("/s/rule-inject")


def test_default_state_dir_when_no_env(isolated_home: Path) -> None:
    """既定の場所を使う（正常系）。"""
    # 実行
    result = paths.default_state_dir({})
    # 検証
    assert result == isolated_home / ".local" / "state" / "rule-inject"


def test_default_log_dir_when_xdg_state_home() -> None:
    """XDG_STATE_HOME の下を使う（正常系）。"""
    # 実行
    result = paths.default_log_dir({"XDG_STATE_HOME": "/s"})
    # 検証
    assert result == Path("/s/rule-inject/logs")


def test_default_log_dir_when_no_env(isolated_home: Path) -> None:
    """既定の場所を使う（正常系）。"""
    # 実行
    result = paths.default_log_dir({})
    # 検証
    assert result == isolated_home / ".local" / "state" / "rule-inject" / "logs"
