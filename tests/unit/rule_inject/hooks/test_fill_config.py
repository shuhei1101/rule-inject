"""hooks/fill_config.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from rule_inject.hooks.fill_config import DECISION_REASON, fill_config

TOOL_PREFIX = "mcp__plugin_rule-inject_rule-inject__"
SEARCH_RULES = f"{TOOL_PREFIX}search_rules"
# 変数参照を持つエントリと、無効にした変数参照のエントリを持つ索引
VARIABLE_INDEX = (
    "rules:\n"
    '  - rule: "!{RULE_ROOT}/a.md"\n'
    "    paths:\n"
    '      - "**/*.py"\n'
    '  - rule: "!{OFF_ROOT}/b.md"\n'
    "    enabled: false\n"
    "    paths:\n"
    '      - "**/*.py"\n'
)
# セッションに無い変数参照を持つ索引
MISSING_INDEX = 'rules:\n  - rule: "!{MISSING}/a.md"\n    paths:\n      - "**/*.py"\n'
# 別のプロジェクトの直下の索引
OTHER_PROJECT_INDEX = 'rules:\n  - rule: "!{OTHER_ROOT}/a.md"\n    paths:\n      - "**/*.py"\n'


def test_fill_config(
    tmp_path: Path,
    settings_env: Callable[..., dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """3 つの環境変数を `session_env` に入れて許可する（正常系）。"""
    # 準備
    env = {
        **settings_env(indexes=[]),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
        "HOME": str(tmp_path / "home"),
    }
    payload = hook_payload(
        "PreToolUse",
        tool_name=SEARCH_RULES,
        tool_input={"path": "/p/a.py", "session_env": {"RULE_INJECT_CONFIG": "/other.yaml"}},
    )
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "allow"
    assert output["permissionDecisionReason"] == DECISION_REASON
    assert output["updatedInput"]["session_env"] == {
        "RULE_INJECT_CONFIG": env["RULE_INJECT_CONFIG"],
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
    }
    assert output["updatedInput"]["path"] == "/p/a.py"


def test_fill_config_when_env_absent(
    tmp_path: Path,
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """無い環境変数はキーに持たない（正常系）。"""
    # 準備
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg_config")}
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={"path": "/p/a.py"})
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    assert result["hookSpecificOutput"]["updatedInput"]["session_env"] == {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
    }


@pytest.mark.parametrize(
    "tool_name",
    [
        pytest.param(f"{TOOL_PREFIX}get_server_status", id="get_server_status"),
        pytest.param(f"{TOOL_PREFIX}reload_settings", id="reload_settings"),
        pytest.param(f"{TOOL_PREFIX}restart_server", id="restart_server"),
        pytest.param(f"{TOOL_PREFIX}update_server", id="update_server"),
        pytest.param("mcp__other__list_rules", id="other_server"),
    ],
)
def test_fill_config_when_tool_not_targeted(
    tool_name: str,
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """対象外のツールには何も返却しない（正常系）。"""
    # 準備
    payload = hook_payload("PreToolUse", tool_name=tool_name, tool_input={})
    # 実行
    result = fill_config(payload, hook_env)
    # 検証
    assert result is None


def test_fill_config_when_input_not_object(
    hook_env: dict[str, str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """`tool_input` がオブジェクトでなければ何も返却しない（正常系）。"""
    # 準備
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES)
    payload["tool_input"] = "path"
    # 実行
    result = fill_config(payload, hook_env)
    # 検証
    assert result is None


def test_fill_config_when_index_has_variable(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """索引に出る変数参照の値も入れる（正常系）。"""
    # 準備
    env = {
        **settings_env(indexes=[str(make_index(VARIABLE_INDEX))]),
        "RULE_ROOT": "/rules",
        "OFF_ROOT": "/off",
        "OTHER": "other",
    }
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={})
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    session_env = result["hookSpecificOutput"]["updatedInput"]["session_env"]
    assert session_env["RULE_ROOT"] == "/rules"
    assert "OFF_ROOT" not in session_env
    assert "OTHER" not in session_env


def test_fill_config_when_variable_unset(
    settings_env: Callable[..., dict[str, str]],
    make_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """セッションに無い変数参照の名前は入れない（正常系）。"""
    # 準備
    env = settings_env(indexes=[str(make_index(MISSING_INDEX))])
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={})
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    assert "MISSING" not in result["hookSpecificOutput"]["updatedInput"]["session_env"]


def test_fill_config_when_settings_unreadable(
    unreadable_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """設定ファイルが読めなくても環境変数を入れる（正常系）。"""
    # 準備
    env = unreadable_env("missing")
    payload = hook_payload("PreToolUse", tool_name=SEARCH_RULES, tool_input={})
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    output = result["hookSpecificOutput"]
    assert output["permissionDecision"] == "allow"
    assert output["updatedInput"]["session_env"]["RULE_INJECT_CONFIG"] == env["RULE_INJECT_CONFIG"]


def test_fill_config_when_project_dir_differs(
    tmp_path: Path,
    settings_env: Callable[..., dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """ツールの `project_dir` のプロジェクトの索引の変数参照の名前を入れる（正常系）。"""
    # 準備
    session_project = tmp_path / "session_project"
    session_project.mkdir()
    other_project = tmp_path / "other_project"
    other_project.mkdir()
    (other_project / "rules.yaml").write_text(OTHER_PROJECT_INDEX, encoding="utf-8")
    env = {
        **settings_env(),
        "CLAUDE_PROJECT_DIR": str(session_project),
        "OTHER_ROOT": "/other",
    }
    payload = hook_payload(
        "PreToolUse",
        tool_name=SEARCH_RULES,
        tool_input={"project_dir": str(other_project)},
    )
    # 実行
    result = fill_config(payload, env)
    # 検証
    assert result is not None
    assert result["hookSpecificOutput"]["updatedInput"]["session_env"]["OTHER_ROOT"] == "/other"
