"""features/migrate/service.py の単体テスト。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from rule_inject.features.migrate import service
from rule_inject.features.migrate.service import apply_migration, plan_migration
from rule_inject.features.migrate.types import SettingsNewerError
from rule_inject.shared.errors import SettingsReadError

TOOL_VERSION = "1.2.3"
NOW = datetime(2026, 11, 6, 1, 2, 3, tzinfo=UTC)


@pytest.fixture(autouse=True)
def tool_version(monkeypatch: pytest.MonkeyPatch) -> str:
    """ツールのバージョンを固定する。"""
    monkeypatch.setattr(service, "_tool_version", lambda: TOOL_VERSION)
    return TOOL_VERSION


def _write(path: Path, text: str) -> Path:
    """設定ファイルを配置する。"""
    path.write_text(text, encoding="utf-8")
    return path


def test_plan_migration(tmp_path: Path) -> None:
    """古い設定の手順を示す（正常系）。"""
    # 準備
    text = "global:\n  server_port: 9000\n"
    path = _write(tmp_path / "settings.yaml", text)
    # 実行
    result = plan_migration(path)
    # 検証
    assert len(result.steps) == 2
    assert "server_port" in result.steps[0]
    assert "1.2.3" in result.steps[1]
    assert result.source_version is None
    assert path.read_text(encoding="utf-8") == text


def test_plan_migration_when_missing(tmp_path: Path) -> None:
    """ファイルが無ければ手順は無い（正常系）。"""
    # 実行
    result = plan_migration(tmp_path / "missing.yaml")
    # 検証
    assert result.steps == ()


def test_plan_migration_when_current(tmp_path: Path) -> None:
    """今のバージョンで適用する手順が無ければ空（正常系）。"""
    # 準備
    path = _write(tmp_path / "settings.yaml", "version: 1.2.3\nglobal:\n  log_dir: /a\n")
    # 実行
    result = plan_migration(path)
    # 検証
    assert result.steps == ()


def test_plan_migration_when_old_version_only(tmp_path: Path) -> None:
    """手順が無くても古いバージョンなら更新する（正常系）。"""
    # 準備
    path = _write(tmp_path / "settings.yaml", "version: 0.0.1\nglobal:\n  log_dir: /a\n")
    # 実行
    result = plan_migration(path)
    # 検証
    assert len(result.steps) == 1
    assert "1.2.3" in result.steps[0]


def test_plan_migration_when_newer(tmp_path: Path) -> None:
    """設定のほうが新しい（異常系）。"""
    # 準備
    path = _write(tmp_path / "settings.yaml", "version: 99.0.0\n")
    # 実行・検証
    with pytest.raises(SettingsNewerError) as raised:
        plan_migration(path)
    assert raised.value.settings_version == "99.0.0"
    assert raised.value.tool_version == "1.2.3"


def test_plan_migration_when_unreadable(tmp_path: Path) -> None:
    """YAML として読み取れない（異常系）。"""
    # 準備
    path = _write(tmp_path / "settings.yaml", "global: [\n")
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        plan_migration(path)
    assert raised.value.path == str(path)


def test_apply_migration(tmp_path: Path) -> None:
    """キーを移してコメントを残す（正常系）。"""
    # 準備
    text = "# 端末の設定\nglobal:\n  # 索引\n  log_dir: /a\n  server_port: 9000\n"
    path = _write(tmp_path / "settings.yaml", text)
    # 実行
    result = apply_migration(path, tmp_path / "bk", now=NOW)
    # 検証
    written = path.read_text(encoding="utf-8")
    assert "server_port" not in written
    assert "version: 1.2.3" in written
    assert "# 端末の設定" in written
    assert "# 索引" in written
    assert result.env == {"RULE_INJECT_PORT": "9000"}
    assert result.backup == str(tmp_path / "bk" / "settings.20261106010203.yaml")
    assert Path(str(result.backup)).read_text(encoding="utf-8") == text


def test_apply_migration_when_no_steps(tmp_path: Path) -> None:
    """手順が無ければ書き換えない（正常系）。"""
    # 準備
    text = "version: 1.2.3\nglobal:\n  log_dir: /a\n"
    path = _write(tmp_path / "settings.yaml", text)
    # 実行
    result = apply_migration(path, tmp_path / "bk", now=NOW)
    # 検証
    assert result.backup is None
    assert path.read_text(encoding="utf-8") == text
    assert not (tmp_path / "bk").exists()
