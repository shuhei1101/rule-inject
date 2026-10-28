"""5 つのツールの本体と、設定・書き込める索引の解決。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from jsonschema.protocols import Validator
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from pydantic import Field

from rule_inject.features.index import (
    match_path,
    match_tool,
    read_index,
)
from rule_inject.features.index.check import check_index
from rule_inject.features.index.edit import IndexLocks, delete_entry, write_entry
from rule_inject.features.index.edit.types import CheckChange
from rule_inject.features.index.types import (
    OPERATIONS,
    EntryOutcome,
    IndexContent,
    IndexEntry,
    Operation,
)
from rule_inject.server._format import fit_page, respond
from rule_inject.server.types import (
    CheckIndexesResult,
    DeleteEntryResult,
    EntryIssue,
    EntryRef,
    IndexIssue,
    IndexReport,
    ListRulesResult,
    ResponseFormat,
    RuleEntry,
    RuleMatch,
    SearchRulesResult,
    WriteEntryResult,
)
from rule_inject.shared.errors import IndexEditError, IndexReadError, SettingsReadError
from rule_inject.shared.settings import CONFIG_ENV, PROJECT_DIR_ENV, Settings, load_settings

# `list_rules` の `limit` の既定と上限
DEFAULT_LIST_LIMIT = 100
MAX_LIST_LIMIT = 500
# `cursor` が受け付ける値（効いているエントリの並びの中の位置を 10 進で書いた文字列）
CURSOR_PATTERN = r"^[0-9]+$"


def _project_settings(project_dir: str, env: Mapping[str, str]) -> Settings:
    """`project_dir` を `CLAUDE_PROJECT_DIR` として、フックと同じ規則で設定を読む。呼び出しのたびに読み直す。"""
    if not os.path.isabs(project_dir):
        raise ToolError(f"project_dir は絶対パスで渡してください: {project_dir}")
    try:
        return load_settings({**env, PROJECT_DIR_ENV: project_dir})
    except SettingsReadError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc


def _config_path(env: Mapping[str, str]) -> str | None:
    """サーバーが読んだ設定ファイルの場所を返す。`RULE_INJECT_CONFIG` が無いときは None。"""
    configured = env.get(CONFIG_ENV)
    return os.path.expanduser(configured) if configured else None


def _editable_index(index: str, settings: Settings) -> str:
    """`index` が設定で読む索引のどれかを確かめ、シンボリックリンクを解いた場所を返す。"""
    resolved = os.path.realpath(os.path.expanduser(index))
    readable = {os.path.realpath(path) for path in settings.indexes}
    if resolved not in readable:
        locations = "、".join(settings.indexes) or "なし"
        raise ToolError(f"{index} は設定ファイルで読む索引でない。読む索引: {locations}")
    return resolved


def _read_indexes(
    settings: Settings, env: Mapping[str, str]
) -> tuple[list[IndexContent], list[IndexIssue]]:
    """設定で読む索引を順に読み、読めた索引と読めなかった索引の理由を返す。"""
    contents: list[IndexContent] = []
    unreadable: list[IndexIssue] = []
    for index in settings.indexes:
        try:
            contents.append(read_index(index, env))
        except IndexReadError as exc:
            unreadable.append(IndexIssue(index=exc.path, reason=exc.reason))
    return contents, unreadable


def _issue(content: IndexContent, outcome: EntryOutcome) -> EntryIssue:
    """読み飛ばした・無効のエントリを、応答の 1 件にする。"""
    return EntryIssue(
        index=content.path,
        position=outcome.position,
        rev=outcome.rev,
        rule=str(outcome.raw["rule"]),
        reason=outcome.reason,
    )


def _rule_entry(content: IndexContent, outcome: EntryOutcome, entry: IndexEntry) -> RuleEntry:
    """効いているエントリを、索引に書いたままのパターンと解いたルールの場所の応答にする。"""
    raw = outcome.raw
    return RuleEntry(
        index=content.path,
        position=outcome.position,
        rev=outcome.rev,
        rule=entry.location,
        paths=list(raw.get("paths", [])),
        exclude=list(raw.get("exclude", [])),
        tools=list(raw.get("tools", [])),
        args=dict(raw.get("args", {})),
        on=[operation for operation in OPERATIONS if operation in entry.on],
        read_by=list(raw.get("read_by", [])),
    )


def _issues(contents: list[IndexContent], status: str) -> list[EntryIssue]:
    """状態が `status` のエントリを、索引の順に応答の一覧にする。"""
    return [
        _issue(content, outcome)
        for content in contents
        for outcome in content.outcomes
        if outcome.status == status
    ]


def list_rules(
    *,
    project_dir: str,
    limit: Annotated[int, Field(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    cursor: Annotated[str | None, Field(pattern=CURSOR_PATTERN)] = None,
    format: ResponseFormat = "markdown",
    env: Mapping[str, str],
) -> CallToolResult:
    """プロジェクトで読む索引と、効いているエントリを返す。読めない索引・読み飛ばしたエントリ・無効のエントリも理由とともに返す。"""
    settings = _project_settings(project_dir, env)
    contents, unreadable = _read_indexes(settings, env)
    effective = [
        _rule_entry(content, outcome, outcome.entry)
        for content in contents
        for outcome in content.outcomes
        if outcome.status == "effective" and outcome.entry is not None
    ]
    skipped = _issues(contents, "skipped")
    disabled = _issues(contents, "disabled")
    start = int(cursor or 0)
    page = effective[start : start + limit]
    # 理由の一覧は先頭のページだけに載せる
    first_page = cursor is None

    def build(count: int) -> ListRulesResult:
        """ページの先頭から count 件を持つ応答を作る。"""
        end = start + count
        return ListRulesResult(
            success=True,
            output=(
                f"索引 {len(settings.indexes)} 件・効いているエントリ {len(effective)} 件・"
                f"読めない索引 {len(unreadable)} 件・読み飛ばしたエントリ {len(skipped)} 件・"
                f"無効のエントリ {len(disabled)} 件"
            ),
            config_path=_config_path(env),
            indexes=list(settings.indexes),
            entries=page[:count],
            unreadable_indexes=unreadable if first_page else [],
            skipped_entries=skipped if first_page else [],
            disabled_entries=disabled if first_page else [],
            total=len(effective),
            next_cursor=str(end) if end < len(effective) else None,
        )

    result, _ = fit_page(build, len(page), format)
    return respond(result, format)


def _search_arguments_error(
    project_dir: str,
    path: str | None,
    operation: Literal["read", "write"] | None,
    tool_name: str | None,
) -> ToolError | None:
    """検索の引数の組み合わせの誤りを、渡し方を添えた ToolError にする。誤りが無ければ None。"""
    if (path is None) == (tool_name is None):
        return ToolError("path か tool_name のどちらか 1 つだけを渡してください")
    if path is not None and operation is None:
        return ToolError("path を渡すときは operation（read か write）も渡してください")
    if path is not None and not os.path.isabs(path):
        return ToolError(f"path は絶対パスで渡してください: {path}")
    return None


def search_rules(
    *,
    project_dir: str,
    path: str | None = None,
    operation: Literal["read", "write"] | None = None,
    tool_name: str | None = None,
    arguments: dict[str, Any] | None = None,
    format: ResponseFormat = "markdown",
    env: Mapping[str, str],
) -> CallToolResult:
    """ファイルのパスと操作の種別か MCP のツールの呼び出しを受け、フックと同じ照合で当たるルールを返す。"""
    error = _search_arguments_error(project_dir, path, operation, tool_name)
    if error is not None:
        raise error
    settings = _project_settings(project_dir, env)
    contents, unreadable = _read_indexes(settings, env)
    used_operation: Operation = operation if path is not None and operation else "mcp"
    # 効いているエントリを 1 件ずつ当て、ルールの場所ごとに初めて当たった順でまとめる
    blocking: dict[str, bool] = {}
    refs: dict[str, list[EntryRef]] = {}
    for content in contents:
        for outcome in content.outcomes:
            if outcome.status != "effective" or outcome.entry is None:
                continue
            if path is not None:
                matched = match_path([outcome.entry], path, used_operation)
            else:
                matched = match_tool([outcome.entry], tool_name or "", arguments or {})
            for rule in matched:
                blocking[rule.location] = blocking.get(rule.location, False) or rule.blocking
                refs.setdefault(rule.location, []).append(
                    EntryRef(index=content.path, position=outcome.position)
                )
    matches = [
        RuleMatch(rule=location, blocking=blocking[location], entries=refs[location])
        for location in blocking
    ]
    result = SearchRulesResult(
        success=True,
        output=(
            f"当たったルール {len(matches)} 件・"
            f"止めるルール {sum(match.blocking for match in matches)} 件"
        ),
        config_path=_config_path(env),
        operation=used_operation,
        matched=matches,
        unreadable_indexes=unreadable,
        skipped_entries=_issues(contents, "skipped"),
    )
    return respond(result, format)


def check_indexes(
    *,
    project_dir: str,
    format: ResponseFormat = "markdown",
    env: Mapping[str, str],
    validator: Validator,
) -> CallToolResult:
    """プロジェクトで読む索引ごとに、フックが読めない理由・JSON Schema への違反・ルールの場所にファイルが無いエントリを返す。"""
    settings = _project_settings(project_dir, env)
    reports: list[IndexReport] = []
    problem_count = 0
    for index in settings.indexes:
        problems = check_index(index, env, validator=validator).problems
        problem_count += len(problems)
        # 問題を種類ごとの一覧に分ける
        reports.append(
            IndexReport(
                index=index,
                hook_error=next(
                    (problem.reason for problem in problems if problem.kind == "hook_error"), None
                ),
                violations=[
                    {"location": problem.location, "reason": problem.reason}
                    for problem in problems
                    if problem.kind == "violation"
                ],
                missing_rules=[
                    {"position": problem.position, "rule": problem.reason}
                    for problem in problems
                    if problem.kind == "missing_rule"
                ],
                skipped_entries=[
                    {"position": problem.position, "reason": problem.reason}
                    for problem in problems
                    if problem.kind == "skipped_entry"
                ],
            )
        )
    result = CheckIndexesResult(
        success=True,
        output=f"索引 {len(reports)} 件・問題 {problem_count} 件",
        config_path=_config_path(env),
        problem_count=problem_count,
        indexes=reports,
    )
    return respond(result, format)


def _write_arguments_error(
    entry: Mapping[str, Any],
    position: int | None,
    expected_rev: str | None,
    remove_keys: list[str] | None,
) -> ToolError | None:
    """書き込みの引数の組み合わせの誤りを、渡し方を添えた ToolError にする。誤りが無ければ None。"""
    if position is not None and expected_rev is None:
        return ToolError("position を渡すときは expected_rev も渡してください")
    if position is None and remove_keys:
        return ToolError("remove_keys は position を渡すときだけ使えます")
    overlapped = sorted(set(remove_keys or []) & set(entry))
    if overlapped:
        return ToolError(f"entry と remove_keys に同じキーがあります: {'、'.join(overlapped)}")
    return None


def write_index_entry(
    *,
    project_dir: str,
    index: str,
    entry: dict[str, Any],
    position: Annotated[int | None, Field(ge=0)] = None,
    expected_rev: str | None = None,
    remove_keys: list[str] | None = None,
    dry_run: bool = False,
    env: Mapping[str, str],
    locks: IndexLocks,
    check_change: CheckChange,
) -> CallToolResult:
    """設定ファイルで読む索引に、エントリを末尾へ新規作成するか、位置で指したエントリのキーを書き換える。"""
    error = _write_arguments_error(entry, position, expected_rev, remove_keys)
    if error is not None:
        raise error
    settings = _project_settings(project_dir, env)
    index_path = _editable_index(index, settings)
    try:
        edited = write_entry(
            index_path,
            entry,
            position=position,
            expected_rev=expected_rev,
            remove_keys=remove_keys or [],
            dry_run=dry_run,
            locks=locks,
            check_change=check_change,
        )
    except IndexEditError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc
    action = "書き込まずに確かめました" if dry_run else "書き込みました"
    result = WriteEntryResult(
        success=True,
        output=f"{edited.index} の rules[{edited.position}] を{action}",
        index=edited.index,
        position=edited.position,
        rev=edited.rev or "",
        written=edited.written,
        diff=edited.diff,
    )
    return respond(result, "json")


def delete_index_entry(
    *,
    project_dir: str,
    index: str,
    position: Annotated[int, Field(ge=0)],
    expected_rev: str,
    dry_run: bool = False,
    env: Mapping[str, str],
    locks: IndexLocks,
) -> CallToolResult:
    """設定ファイルで読む索引から、位置で指したエントリを削除する。"""
    settings = _project_settings(project_dir, env)
    index_path = _editable_index(index, settings)
    try:
        edited = delete_entry(
            index_path, position=position, expected_rev=expected_rev, dry_run=dry_run, locks=locks
        )
    except IndexEditError as exc:
        raise ToolError(f"{exc.path}: {exc.reason}") from exc
    action = "削除せずに確かめました" if dry_run else "削除しました"
    result = DeleteEntryResult(
        success=True,
        output=f"{edited.index} の rules[{edited.position}] を{action}",
        index=edited.index,
        rule=edited.rule or "",
        written=edited.written,
        diff=edited.diff,
    )
    return respond(result, "json")
