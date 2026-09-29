"""features/command/service.py の単体テスト。"""

from __future__ import annotations

from pathlib import Path

from rule_inject.features.command.service import (
    FULL_READ_COMMANDS,
    READ_COMMANDS,
    extract_read_paths,
)


def test_extract_read_paths(tmp_path: Path) -> None:
    """cd とパイプをまたいでパスを取り出す（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print()\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("cd src && cat app.py | head -n 5", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "src" / "app.py")]


def test_extract_read_paths_when_pattern_arg(tmp_path: Path) -> None:
    """実在しない引数を捨てる（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("grep -n foo a.md", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "a.md")]


def test_extract_read_paths_when_not_full_read(tmp_path: Path) -> None:
    """対象外のコマンドは見ない（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("grep foo a.md", tmp_path, FULL_READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_unparsable(tmp_path: Path) -> None:
    """分けられないコマンドは空を返す（正常系）。"""
    # 実行
    result = extract_read_paths('cat "a.md', tmp_path, READ_COMMANDS)
    # 検証
    assert result == []
