"""ツールの引数への設定の記入（PreToolUse）。rule-inject の MCP のツールにセッションの設定を入れる。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from rule_inject.features.index import read_index
from rule_inject.shared.errors import IndexReadError, PromptLoadError, SettingsReadError
from rule_inject.shared.logger import Component, LogOperation, write_log
from rule_inject.shared.paths import default_log_dir
from rule_inject.shared.prompts import load_hook_prompt
from rule_inject.shared.settings import PROJECT_DIR_ENV, SESSION_ENV_KEYS, load_settings
from rule_inject.shared.variables import variable_names

# rule-inject の MCP のツールの完全名の前半
TOOL_PREFIX = "mcp__plugin_rule-inject_rule-inject__"
# `session_env` を入れるツール（サーバー自身を扱うツールは入れない）
TARGET_TOOLS = frozenset(
    {
        "list_rules",
        "search_rules",
        "check_indexes",
        "write_index_entry",
        "delete_index_entry",
        "get_read_records",
        "delete_read_records",
    }
)
# `updatedInput` に入れる引数の名前
SESSION_ENV_ARG = "session_env"
# `permissionDecisionReason` の文面のプロンプトの名前
DECISION_REASON = "fill-config-reason"


def _index_variable_names(env: Mapping[str, str], project_dir: object) -> tuple[str, ...]:
    """ツールの `project_dir`（無ければセッションのプロジェクト）で読み込む索引の `rule` に出る変数参照の名前を返却する。"""
    # サーバーが `project_dir` を `CLAUDE_PROJECT_DIR` として扱うのとそろえる
    settings_env: Mapping[str, str] = (
        {**env, PROJECT_DIR_ENV: project_dir}
        if isinstance(project_dir, str) and os.path.isabs(project_dir)
        else env
    )
    # 設定ファイルが読めなければ名前を加えない（3 つの環境変数だけで動かす）
    try:
        settings = load_settings(settings_env)
    except SettingsReadError:
        return ()
    names: list[str] = []
    for index_path in settings.indexes:
        # 読めない索引は飛ばす（ルール案内が通知する）
        try:
            content = read_index(index_path, settings_env)
        except IndexReadError:
            continue
        # 無効のエントリは照合に使用しないため、その名前は入れない
        for outcome in content.outcomes:
            if outcome.status != "disabled":
                names.extend(variable_names(str(outcome.raw["rule"])))
    return tuple(dict.fromkeys(names))


def fill_config(payload: dict[str, Any], env: Mapping[str, str]) -> dict[str, Any] | None:
    """対象のツールの入力にセッションの設定を `session_env` として上書きで入れ、許可する PreToolUse の出力を作る。"""
    tool_name = payload.get("tool_name", "")
    # 対象外のツールには何も出さない
    if not tool_name.startswith(TOOL_PREFIX) or tool_name[len(TOOL_PREFIX) :] not in TARGET_TOOLS:
        return None
    tool_input = payload.get("tool_input")
    # 入力がオブジェクトでなければ書き換えない
    if not isinstance(tool_input, dict):
        return None
    session_env = {key: env[key] for key in SESSION_ENV_KEYS if key in env}
    # 索引の変数参照の名前のうち、セッションにあるものだけを入れる
    for name in _index_variable_names(env, tool_input.get("project_dir")):
        if name in env:
            session_env[name] = env[name]
    output: dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "updatedInput": {**tool_input, SESSION_ENV_ARG: session_env},
    }
    # 許可の理由のプロンプトファイルが読めなければ、理由を除いて入力の書き換えを続ける
    try:
        output["permissionDecisionReason"] = load_hook_prompt(DECISION_REASON)
    except PromptLoadError as exc:
        _log_prompt_failure(exc, env, payload.get("session_id"))
    return {"hookSpecificOutput": output}


def _log_prompt_failure(error: PromptLoadError, env: Mapping[str, str], session_id: object) -> None:
    """許可の理由のプロンプトファイルを読めなかったことをログへ書き込む。"""
    try:
        log_folder = load_settings(env).log_dir
    except SettingsReadError:
        log_folder = default_log_dir(env)
    write_log(
        log_folder,
        component=Component.FILL_CONFIG,
        operation=LogOperation.READ_PROMPT,
        reason=error.reason,
        session_id=session_id if isinstance(session_id, str) else None,
        path=error.path,
    )
