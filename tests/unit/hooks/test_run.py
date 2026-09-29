"""hooks/run.py の単体テスト。"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RUN_PY = Path(__file__).resolve().parents[3] / "hooks" / "run.py"


@pytest.fixture
def run_module() -> ModuleType:
    """hooks/run.py をモジュールとして読み込む。"""
    spec = importlib.util.spec_from_file_location("hook_run", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def imported_rule_inject_modules() -> Callable[[], list[str]]:
    """import 済みの rule_inject のモジュール名を返す関数。"""

    def _names() -> list[str]:
        """sys.modules にある rule_inject 配下のモジュール名を返す。"""
        return [name for name in sys.modules if name.split(".")[0] == "rule_inject"]

    return _names


@pytest.fixture
def without_rule_inject(
    monkeypatch: pytest.MonkeyPatch,
    imported_rule_inject_modules: Callable[[], list[str]],
) -> None:
    """import 済みの rule_inject のモジュールを外し、テストの後に戻す。"""
    for name in imported_rule_inject_modules():
        monkeypatch.delitem(sys.modules, name)


def test_main(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """子プロセスとして動かして終了コード 0 を返す（正常系）。"""
    # 準備
    payload = hook_payload("SessionStart", source="startup")
    # 実行
    completed = subprocess.run(
        [sys.executable, str(RUN_PY), "work_rules"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **hook_env},
        check=False,
    )
    # 検証
    assert completed.returncode == 0
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["additionalContext"]


def test_main_when_python_too_old(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_module: ModuleType,
    state_dir: Path,
    hook_payload: Callable[..., dict[str, Any]],
    imported_rule_inject_modules: Callable[[], list[str]],
    without_rule_inject: None,
) -> None:
    """版が足りないとき知らせて終える（正常系）。"""
    # 準備
    monkeypatch.setenv("RULE_INJECT_STATE_DIR", str(state_dir))
    payload = hook_payload("PreToolUse", tool_name="Write", tool_input={"file_path": "/p/a.py"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0))
    # 実行
    code = run_module.main(["rule_guide"])
    # 検証
    assert code == 0
    context = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "3.12" in context
    assert "3.11" in context
    assert imported_rule_inject_modules() == []


def test_main_when_python_too_old_and_sweep_read(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    run_module: ModuleType,
    state_dir: Path,
    log_folder: Path,
    hook_payload: Callable[..., dict[str, Any]],
    read_lines: Callable[[Path], list[str]],
    without_rule_inject: None,
) -> None:
    """掃除のフックは版が足りなくても知らせを重ねない（正常系）。"""
    # 準備
    monkeypatch.setenv("RULE_INJECT_STATE_DIR", str(state_dir))
    monkeypatch.setenv("RULE_INJECT_LOG_DIR", str(log_folder))
    payload = hook_payload("SessionStart", source="startup")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0))
    # 実行
    code = run_module.main(["sweep_read"])
    # 検証
    assert code == 0
    assert capsys.readouterr().out == ""
    today_log = log_folder / f"{datetime.now(UTC):%Y%m%d}_rule-inject.log"
    assert len(read_lines(today_log)) == 1
    assert not (state_dir / "rule-inject.log").exists()
