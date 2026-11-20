"""インターフェース定義『ツールの引数への設定の記入』の結合テスト。"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
HOOK_RUN = PROJECT_ROOT / "hooks" / "run.py"
HOOK_TIMEOUT_SEC = 30
SEARCH_RULES = "mcp__plugin_rule-inject_rule-inject__search_rules"
GET_SERVER_STATUS = "mcp__plugin_rule-inject_rule-inject__get_server_status"


@pytest.fixture
def run_fill_config() -> Callable[..., subprocess.CompletedProcess[str]]:
    """環境変数を指定したとおりに組み立ててフック `fill_config` を子プロセスとして起動する factory。"""

    def _run(env: Mapping[str, str], stdin: str) -> subprocess.CompletedProcess[str]:
        """env だけを環境変数にし（`PATH` と `HOME` は引き継ぐ）、stdin を標準入力へ引き渡す。"""
        return subprocess.run(
            [sys.executable, str(HOOK_RUN), "fill_config"],
            input=stdin,
            capture_output=True,
            text=True,
            env=dict(env),
            timeout=HOOK_TIMEOUT_SEC,
            check=False,
        )

    return _run


@pytest.fixture
def isolated_env(tmp_path: Path) -> dict[str, str]:
    """このプラグインと XDG の環境変数を持たず、`PATH`・`HOME`・`CLAUDE_PROJECT_DIR` だけを持つ環境変数。"""
    home = tmp_path / "home"
    home.mkdir()
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }


def test_normal(
    tmp_path: Path,
    isolated_env: dict[str, str],
    run_fill_config: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """`tool_input` にセッションの設定を決める環境変数を `session_env` として入れ、許可する（正常系）。"""
    # 準備
    config = tmp_path / "config" / "settings.yaml"
    config.parent.mkdir()
    config.write_text("global:\n  indexes: []\n", encoding="utf-8")
    env = {
        **isolated_env,
        "RULE_INJECT_CONFIG": str(config),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
        "UNRELATED": "value",
    }
    payload = hook_payload(
        "PreToolUse",
        tool_name=SEARCH_RULES,
        tool_input={
            "project_dir": str(tmp_path),
            "path": "/p/a.py",
            "session_env": {"RULE_INJECT_CONFIG": "/other/settings.yaml"},
        },
    )
    # 実行
    completed = run_fill_config(env, json.dumps(payload))
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["updatedInput"]["session_env"] == {
        "RULE_INJECT_CONFIG": str(config),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
    }
    assert output["updatedInput"]["project_dir"] == str(tmp_path)
    assert output["updatedInput"]["path"] == "/p/a.py"
    assert output["permissionDecision"] == "allow"
    assert completed.returncode == 0


def test_normal_when_env_absent(
    tmp_path: Path,
    isolated_env: dict[str, str],
    run_fill_config: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """セッションに無い環境変数は `session_env` のキーに持たない（正常系）。"""
    # 準備
    env = {**isolated_env, "XDG_CONFIG_HOME": str(tmp_path / "xdg_config")}
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={"path": "/p/a.py"})
    # 実行
    completed = run_fill_config(env, json.dumps(payload))
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["updatedInput"]["session_env"] == {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
    }
    assert completed.returncode == 0


def test_normal_when_tool_not_targeted(
    isolated_env: dict[str, str],
    run_fill_config: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """設定を引数に取らないツールには何も出さない（正常系）。"""
    # 準備
    payload = hook_payload("PreToolUse", tool_name=GET_SERVER_STATUS, tool_input={})
    # 実行
    completed = run_fill_config(isolated_env, json.dumps(payload))
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_input_unparsable(
    isolated_env: dict[str, str],
    run_fill_config: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """標準入力が JSON として読めなければ何も出さない（正常系）。"""
    # 実行
    completed = run_fill_config(isolated_env, "{not json")
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_index_has_variable(
    tmp_path: Path,
    isolated_env: dict[str, str],
    run_fill_config: Callable[..., subprocess.CompletedProcess[str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """索引の `rule` に出る `!{名前}` の値も `session_env` に入れる（正常系）。"""
    # 準備
    index = tmp_path / "index.yaml"
    index.write_text(
        'rules:\n  - rule: "!{RULE_ROOT}/a.md"\n    paths:\n      - "**/*.py"\n',
        encoding="utf-8",
    )
    config = tmp_path / "config" / "settings.yaml"
    config.parent.mkdir()
    config.write_text(f'global:\n  indexes:\n    - "{index}"\n', encoding="utf-8")
    env = {
        **isolated_env,
        "RULE_INJECT_CONFIG": str(config),
        "RULE_ROOT": "/rules",
        "UNRELATED": "value",
    }
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={"path": "/p/a.py"})
    # 実行
    completed = run_fill_config(env, json.dumps(payload))
    # 検証
    session_env = json.loads(completed.stdout)["hookSpecificOutput"]["updatedInput"]["session_env"]
    assert session_env["RULE_ROOT"] == "/rules"
    assert "UNRELATED" not in session_env
    assert completed.returncode == 0
