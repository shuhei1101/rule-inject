"""build_skills/__main__.py の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """書き換えたパスを出す（正常系）。"""
    from rule_inject.build_skills import __main__ as entry

    # 準備
    monkeypatch.setattr(entry, "build_skills", lambda _root: ("skills/a/SKILL.md",))
    # 実行
    entry.main()
    # 検証
    assert capsys.readouterr().out == "skills/a/SKILL.md\n"


def test_main_when_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """生成の誤り（異常系）。"""
    from rule_inject.build_skills import __main__ as entry
    from rule_inject.features.build_skills.types import SkillBuildError

    def fail(_root: Path) -> tuple[str, ...]:
        """生成の誤りを送出する。"""
        raise SkillBuildError(("docs/agent-flow/a.yaml: skill.path",))

    # 準備
    monkeypatch.setattr(entry, "build_skills", fail)
    # 実行
    with pytest.raises(SystemExit) as caught:
        entry.main()
    # 検証
    assert caught.value.code == 2
    assert capsys.readouterr().err == "docs/agent-flow/a.yaml: skill.path\n"
