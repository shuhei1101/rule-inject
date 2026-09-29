"""索引の読み込みと、パス・ツール名の照合。"""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from rule_inject.features.index._yaml import parse_index
from rule_inject.features.index.types import (
    DEFAULT_ON,
    IndexEntry,
    IndexLoadResult,
    MatchedRule,
    Operation,
)
from rule_inject.shared.errors import IndexReadError, describe
from rule_inject.shared.paths import resolve_location

# 読む順に並べた、索引を指す環境変数の名前
INDEX_ENV_NAMES = ("RULE_INJECT_INDEXES_USER", "RULE_INJECT_INDEXES_PROJECT")
PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
INDEX_SEPARATOR = ","


def _index_paths(env: Mapping[str, str]) -> list[str]:
    """環境変数が指す索引のパスを、読む順に並べる。"""
    paths: list[str] = []
    for name in INDEX_ENV_NAMES:
        # カンマで分けて前後の空白を落とし、空の項目は読まない
        for item in env.get(name, "").split(INDEX_SEPARATOR):
            if item.strip():
                paths.append(item.strip())
    return paths


def _load_index(index_path: str, project_dir: str | None) -> tuple[IndexEntry, ...]:
    """索引 1 つを読んでエントリにする。読めなければ IndexReadError を送出する。"""
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
    # `rule` を索引のフォルダから解き、`on` が無ければ索引の既定で埋める
    fallback_on = frozenset(default_on or DEFAULT_ON)
    return tuple(
        IndexEntry(
            location=resolve_location(str(raw["rule"]), resolved.parent),
            paths=tuple(raw.get("paths", ())),
            exclude=tuple(raw.get("exclude", ())),
            tools=tuple(raw.get("tools", ())),
            on=frozenset(raw["on"]) if "on" in raw else fallback_on,
        )
        for raw in raw_entries
    )


def load_indexes(env: Mapping[str, str]) -> IndexLoadResult:
    """環境変数が指す全ての索引を読み、読めたエントリと読めなかった索引を返す。"""
    project_dir = env.get(PROJECT_DIR_ENV)
    entries: list[IndexEntry] = []
    failures: list[IndexReadError] = []
    for index_path in _index_paths(env):
        # 読めない索引は集めて、次の索引へ進む
        try:
            entries.extend(_load_index(index_path, project_dir))
        except IndexReadError as exc:
            failures.append(exc)
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


def match_path(entries: Sequence[IndexEntry], path: str, operation: Operation) -> list[MatchedRule]:
    """対象のパスに当たるエントリをルールごとに 1 件へまとめる。"""
    matched = [
        entry
        for entry in entries
        if any(_glob_match(pattern, path) for pattern in entry.paths)
        and not any(_glob_match(pattern, path) for pattern in entry.exclude)
    ]
    return _merge(matched, operation)


def match_tool(entries: Sequence[IndexEntry], tool_name: str) -> list[MatchedRule]:
    """MCP のツール名に当たるエントリをルールごとに 1 件へまとめる。"""
    matched = [
        entry
        for entry in entries
        if any(fnmatch.fnmatchcase(tool_name, pattern) for pattern in entry.tools)
    ]
    return _merge(matched, "mcp")


def rule_locations(entries: Sequence[IndexEntry]) -> frozenset[str]:
    """索引に載ったルールの場所の集合を返す。"""
    return frozenset(entry.location for entry in entries)
