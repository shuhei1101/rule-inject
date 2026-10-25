"""索引の読み込みと、パス・ツール名の照合。"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from rule_inject.features.index._yaml import parse_index
from rule_inject.features.index.types import (
    DEFAULT_ON,
    ArgCondition,
    IndexEntry,
    IndexLoadResult,
    MatchedRule,
    MatchPattern,
    Operation,
    ReadByCondition,
)
from rule_inject.shared.errors import IndexReadError, describe
from rule_inject.shared.paths import resolve_location
from rule_inject.shared.variables import expand_variables

# 読む順に並べた、索引を指す環境変数の名前
INDEX_ENV_NAMES = ("RULE_INJECT_INDEXES_USER", "RULE_INJECT_INDEXES_PROJECT")
USER_INDEX_ENV, PROJECT_INDEX_ENV = INDEX_ENV_NAMES
# 環境変数が無いときに読む索引の、設定フォルダと `CLAUDE_PROJECT_DIR` からのパス
USER_INDEX_DEFAULT = "rule-inject/rules.yaml"
PROJECT_INDEX_DEFAULT = "rules.yaml"
CONFIG_HOME_ENV = "XDG_CONFIG_HOME"
DEFAULT_CONFIG_HOME = "~/.config"
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
INDEX_SEPARATOR = ","
NAME_SEPARATOR = "、"
# 先頭がこの文字列のパターンは、残りを正規表現として読む
REGEX_PREFIX = "re:"
# 引数のキーをオブジェクトの子へたどる区切り
ARG_KEY_SEPARATOR = "."
# Read で読めないため読み飛ばす `rule` の頭
URL_SCHEMES = ("http://", "https://")


def _default_index_path(name: str, env: Mapping[str, str]) -> str | None:
    """環境変数が無いときに読む索引の既定のパスを返す。置き場所が決まらないか、ファイルが無ければ None。"""
    if name == USER_INDEX_ENV:
        # 設定フォルダは XDG_CONFIG_HOME（無いか空なら ~/.config）
        config_home = env.get(CONFIG_HOME_ENV) or DEFAULT_CONFIG_HOME
        candidate = Path(config_home).expanduser() / USER_INDEX_DEFAULT
    else:
        project_dir = env.get(PROJECT_DIR_ENV)
        # プロジェクトの直下が分からなければ、既定の置き場所も決まらない
        if not project_dir:
            return None
        candidate = Path(project_dir) / PROJECT_INDEX_DEFAULT
    # 既定の置き場所にファイルが無いのは失敗ではなく、索引を置いていない状態
    return str(candidate) if candidate.exists() else None


def _index_paths(env: Mapping[str, str]) -> list[str]:
    """環境変数か既定の置き場所が指す索引のパスを、読む順に並べる。"""
    paths: list[str] = []
    for name in INDEX_ENV_NAMES:
        # 環境変数が無ければ既定の置き場所を読む
        if name not in env:
            default_path = _default_index_path(name, env)
            if default_path is not None:
                paths.append(default_path)
            continue
        # カンマで分けて前後の空白を落とし、空の項目は読まない（空の文字列は何も読まない）
        for item in env[name].split(INDEX_SEPARATOR):
            if item.strip():
                paths.append(item.strip())
    return paths


def _compile_pattern(source: str) -> MatchPattern:
    """索引に書かれたパターンを `MatchPattern` にする。`re:` で始まれば残りを正規表現にコンパイルする。"""
    if source.startswith(REGEX_PREFIX):
        return MatchPattern(source=source, regex=re.compile(source[len(REGEX_PREFIX) :]))
    return MatchPattern(source=source, regex=None)


def _compile_patterns(sources: Sequence[str]) -> tuple[MatchPattern, ...]:
    """パターンの並びを `MatchPattern` の並びにする。読めない正規表現は、書かれたパターンと理由を持つ IndexReadError にする。"""
    patterns: list[MatchPattern] = []
    for source in sources:
        try:
            patterns.append(_compile_pattern(source))
        except re.error as exc:
            raise IndexReadError(
                path="", reason=f"パターン {source} の正規表現を読めない: {exc}"
            ) from exc
    return tuple(patterns)


def _compile_arg_conditions(raw_args: Mapping[str, Sequence[str]]) -> tuple[ArgCondition, ...]:
    """キーごとのパターンのリストを `ArgCondition` の並びにする。"""
    return tuple(
        ArgCondition(key=key, patterns=_compile_patterns(sources))
        for key, sources in raw_args.items()
    )


def _build_entry(
    raw: Mapping[str, Any], location: str, fallback_on: frozenset[Operation]
) -> IndexEntry:
    """読み取ったエントリのキーと値から、パターンをコンパイルした IndexEntry を作る。"""
    return IndexEntry(
        location=location,
        paths=_compile_patterns(raw.get("paths", ())),
        exclude=_compile_patterns(raw.get("exclude", ())),
        tools=_compile_patterns(raw.get("tools", ())),
        args=_compile_arg_conditions(raw.get("args", {})),
        on=frozenset(raw["on"]) if "on" in raw else fallback_on,
        read_by=tuple(
            ReadByCondition(
                tools=_compile_patterns(item["tools"]),
                args=_compile_arg_conditions(item.get("args", {})),
            )
            for item in raw.get("read_by", ())
        ),
    )


def _load_index(
    index_path: str, project_dir: str | None, env: Mapping[str, str]
) -> tuple[tuple[IndexEntry, ...], tuple[IndexReadError, ...]]:
    """索引 1 つを読んでエントリにし、展開できずに読み飛ばしたエントリの理由を添える。読めなければ IndexReadError を送出する。"""
    # 相対パスの索引は、プロジェクトの直下が分かるときだけ解ける
    if not os.path.isabs(os.path.expanduser(index_path)) and project_dir is None:
        raise IndexReadError(
            path=index_path, reason="環境変数 CLAUDE_PROJECT_DIR が無く、相対パスを解けません"
        )
    resolved = Path(resolve_location(index_path, Path(project_dir or "/")))
    try:
        default_on, raw_entries = parse_index(resolved.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IndexReadError(path=str(resolved), reason=describe(exc)) from exc
    fallback_on = frozenset(default_on or DEFAULT_ON)
    entries: list[IndexEntry] = []
    skipped: list[IndexReadError] = []
    for raw in raw_entries:
        # `rule` の変数参照を展開する。展開できない名前が残ったエントリは読み飛ばして理由を残す
        written_rule = str(raw["rule"])
        expansion = expand_variables(written_rule, env)
        if expansion.unresolved:
            names = NAME_SEPARATOR.join(expansion.unresolved)
            skipped.append(
                IndexReadError(
                    path=str(resolved),
                    reason=f"rule {written_rule} の変数参照を展開できない: {names}",
                )
            )
            continue
        # URL の `rule` は Read で読めないため、読み飛ばして理由を残す
        if expansion.text.startswith(URL_SCHEMES):
            skipped.append(
                IndexReadError(
                    path=str(resolved),
                    reason=f"rule {expansion.text} は URL のため Read で読めない",
                )
            )
            continue
        # 展開した `rule` を索引のフォルダから解き、`on` が無ければ索引の既定で埋める。
        # 読めない正規表現を持つエントリは読み飛ばして理由を残す
        try:
            entries.append(
                _build_entry(raw, resolve_location(expansion.text, resolved.parent), fallback_on)
            )
        except IndexReadError as exc:
            skipped.append(IndexReadError(path=str(resolved), reason=exc.reason))
    return tuple(entries), tuple(skipped)


def load_indexes(env: Mapping[str, str]) -> IndexLoadResult:
    """環境変数か既定の置き場所が指す全ての索引を読み、読めたエントリと読めなかった索引・読み飛ばしたエントリを返す。"""
    project_dir = env.get(PROJECT_DIR_ENV)
    entries: list[IndexEntry] = []
    failures: list[IndexReadError] = []
    for index_path in _index_paths(env):
        # 読めない索引は集めて、次の索引へ進む
        try:
            loaded, skipped = _load_index(index_path, project_dir, env)
        except IndexReadError as exc:
            failures.append(exc)
            continue
        entries.extend(loaded)
        failures.extend(skipped)
    return IndexLoadResult(entries=tuple(entries), failures=tuple(failures))


def _translate_alternatives(pattern: str, start: int) -> tuple[str, int] | None:
    """`{a,b}` の候補を正規表現の選択に読み替え、`}` の次の位置とともに返す。閉じていなければ None。"""
    end = pattern.find("}", start)
    if end == -1:
        return None
    alternatives = [_translate(item) for item in pattern[start + 1 : end].split(",")]
    return "(?:" + "|".join(alternatives) + ")", end + 1


def _translate(pattern: str) -> str:
    """glob を正規表現に読み替える（`**/` は 0 個以上のフォルダ、`*` は `/` を含まない文字列）。"""
    result: list[str] = []
    position = 0
    while position < len(pattern):
        # `**/` は 0 個以上のフォルダ、それ以外の `**` は `/` も含む任意の文字列
        if pattern.startswith("**/", position):
            result.append("(?:.*/)?")
            position += 3
        elif pattern.startswith("**", position):
            result.append(".*")
            position += 2
        elif pattern[position] == "*":
            result.append("[^/]*")
            position += 1
        elif pattern[position] == "?":
            result.append("[^/]")
            position += 1
        elif pattern[position] == "{" and (
            alternatives := _translate_alternatives(pattern, position)
        ):
            regex, position = alternatives
            result.append(regex)
        else:
            result.append(re.escape(pattern[position]))
            position += 1
    return "".join(result)


def _glob_match(pattern: str, path: str) -> bool:
    """`**` をフォルダをまたぐ一致として扱い、絶対パスに glob を当てる。"""
    return re.fullmatch(_translate(pattern), path) is not None


def _merge(entries: Sequence[IndexEntry], operation: Operation) -> list[MatchedRule]:
    """同じルールの場所のエントリを 1 件にまとめ、どれかが止めるなら止める。"""
    blocking_by_location: dict[str, bool] = {}
    for entry in entries:
        blocking = operation in entry.on
        blocking_by_location[entry.location] = (
            blocking_by_location.get(entry.location, False) or blocking
        )
    return [
        MatchedRule(location=location, blocking=blocking)
        for location, blocking in blocking_by_location.items()
    ]


def _fnmatch_glob(pattern: str, value: str) -> bool:
    """ツール名と引数の値に glob を当てる（`fnmatch` の引数の順をパターン・値にそろえる）。"""
    return fnmatch.fnmatchcase(value, pattern)


def _match_pattern(
    pattern: MatchPattern, value: str, *, glob_match: Callable[[str, str], bool]
) -> bool:
    """値にパターンを当てる。正規表現は部分一致、glob は渡された照合で当てる。"""
    if pattern.regex is not None:
        return pattern.regex.search(value) is not None
    return glob_match(pattern.source, value)


def _expand_arrays(nodes: Sequence[Any]) -> list[Any]:
    """配列は要素に開き、それ以外の値はそのまま並べる（配列の中の配列は開かない）。"""
    expanded: list[Any] = []
    for node in nodes:
        if isinstance(node, list):
            expanded.extend(node)
        else:
            expanded.append(node)
    return expanded


def _argument_values(tool_input: Mapping[str, Any], key: str) -> list[str]:
    """ドット区切りのキーが指す引数の値を、照合する文字列の並びにする。キーが無ければ空。"""
    nodes: list[Any] = [tool_input]
    # 先頭から順にたどる。途中の配列は要素ごとにたどり、オブジェクトでない値と無いキーは捨てる
    for part in key.split(ARG_KEY_SEPARATOR):
        nodes = [
            node[part]
            for node in _expand_arrays(nodes)
            if isinstance(node, Mapping) and part in node
        ]
    values: list[str] = []
    for node in _expand_arrays(nodes):
        # 文字列はそのまま、文字列以外のスカラーは JSON の表記にし、オブジェクトと配列は捨てる
        if isinstance(node, str):
            values.append(node)
        elif not isinstance(node, Mapping | list):
            values.append(json.dumps(node))
    return values


def _match_args(conditions: Sequence[ArgCondition], tool_input: Mapping[str, Any]) -> bool:
    """全てのキーについて、値のどれかがパターンのどれかに当たるか。値が 1 つも無いキーは当たらない。"""
    return all(
        any(
            _match_pattern(pattern, value, glob_match=_fnmatch_glob)
            for value in _argument_values(tool_input, condition.key)
            for pattern in condition.patterns
        )
        for condition in conditions
    )


def match_path(entries: Sequence[IndexEntry], path: str, operation: Operation) -> list[MatchedRule]:
    """対象のパスに当たるエントリをルールごとに 1 件へまとめる。"""
    matched = [
        entry
        for entry in entries
        if any(_match_pattern(pattern, path, glob_match=_glob_match) for pattern in entry.paths)
        and not any(
            _match_pattern(pattern, path, glob_match=_glob_match) for pattern in entry.exclude
        )
    ]
    return _merge(matched, operation)


def match_tool(
    entries: Sequence[IndexEntry], tool_name: str, tool_input: Mapping[str, Any]
) -> list[MatchedRule]:
    """MCP のツール名と引数に当たるエントリをルールごとに 1 件へまとめる。"""
    matched = [
        entry
        for entry in entries
        if any(
            _match_pattern(pattern, tool_name, glob_match=_fnmatch_glob) for pattern in entry.tools
        )
        and _match_args(entry.args, tool_input)
    ]
    return _merge(matched, "mcp")


def match_read_by(
    entries: Sequence[IndexEntry], tool_name: str, tool_input: Mapping[str, Any]
) -> list[str]:
    """MCP のツールの呼び出しが `read_by` に当たるエントリのルールの場所を、索引の順に重なりを落として返す。"""
    # 案内用の tools・args は見ず、read_by の要素のどれか 1 つに当たるエントリだけを選ぶ
    locations = [
        entry.location
        for entry in entries
        if any(
            any(
                _match_pattern(pattern, tool_name, glob_match=_fnmatch_glob)
                for pattern in condition.tools
            )
            and _match_args(condition.args, tool_input)
            for condition in entry.read_by
        )
    ]
    return list(dict.fromkeys(locations))


def rule_locations(entries: Sequence[IndexEntry]) -> frozenset[str]:
    """索引に載ったルールの場所の集合を返す。"""
    return frozenset(entry.location for entry in entries)
