"""migrate/__main__.py の単体テスト。"""

from __future__ import annotations

import json
import sys

import pytest

from rule_inject.features.migrate.types import MigrationResult, SettingsNewerError
from rule_inject.migrate import __main__ as entry
from rule_inject.shared.errors import SettingsReadError


def test_main_when_plan(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """手順を JSON で書く（正常系）。"""
    # 準備
    result = MigrationResult(
        source_version=None,
        target_version="1.2.3",
        steps=("手順", "version を 1.2.3 にする"),
        migrations=("手順",),
        backup=None,
        env={},
    )
    monkeypatch.setattr(sys, "argv", ["migrate", "--plan"])
    monkeypatch.setattr(entry, "plan_migration", lambda _path: result)
    # 実行
    entry.main()
    # 検証
    assert json.loads(capsys.readouterr().out) == {
        "from": None,
        "to": "1.2.3",
        "steps": ["手順", "version を 1.2.3 にする"],
        "migrations": ["手順"],
        "backup": None,
        "env": {},
    }


def test_main_when_newer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """設定が新しい（異常系）。"""

    # 準備
    def _raise(_path: object) -> MigrationResult:
        """設定が新しい誤りを送出する。"""
        raise SettingsNewerError(settings_version="99.0.0", tool_version="1.2.3")

    monkeypatch.setattr(sys, "argv", ["migrate", "--plan"])
    monkeypatch.setattr(entry, "plan_migration", _raise)
    # 実行・検証
    with pytest.raises(SystemExit) as raised:
        entry.main()
    assert raised.value.code == 6
    stderr = capsys.readouterr().err
    assert "99.0.0" in stderr
    assert "1.2.3" in stderr


def test_main_when_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """設定ファイルが読み取れない（異常系）。"""

    # 準備
    def _raise(_path: object, _backup: object, *, now: object) -> MigrationResult:
        """読み取りの誤りを送出する。"""
        raise SettingsReadError(path="/c.yaml", reason="理由")

    monkeypatch.setattr(sys, "argv", ["migrate"])
    monkeypatch.setattr(entry, "apply_migration", _raise)
    # 実行・検証
    with pytest.raises(SystemExit) as raised:
        entry.main()
    assert raised.value.code == 1
    assert "/c.yaml: 理由" in capsys.readouterr().err
