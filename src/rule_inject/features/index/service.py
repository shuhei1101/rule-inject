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
    RejectedLocation,
    SelectedLocations,
)
from rule_inject.shared.errors import IndexReadError, describe
from rule_inject.shared.paths import URL_SCHEMES, resolve_location
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
HOME_MARK = "~"
NOT_IN_INDEX_REASON = "索引に載っていない場所"
RELATIVE_LOCATION_REASON = "相対パスは読まない。絶対パス・~・https:// の URL で渡す"
RELATIVE_PATH_REASON = "相対パスは照合しない。絶対パスで渡す"


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
        # 展開した `rule` を索引のフォルダから解き、`on` が無ければ索引の既定で埋める
        entries.append(
            IndexEntry(
                location=resolve_location(expansion.text, resolved.parent),
                paths=tuple(raw.get("paths", ())),
                exclude=tuple(raw.get("exclude", ())),
                tools=tuple(raw.get("tools", ())),
                on=frozenset(raw["on"]) if "on" in raw else fallback_on,
            )
        )
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


def _is_absolute_location(location: str) -> bool:
    """場所が、絶対パス・`~` で始まるパス・URL のどれかかを返す。"""
    return location.startswith((*URL_SCHEMES, HOME_MARK)) or os.path.isabs(location)


def select_locations(
    entries: Sequence[IndexEntry], locations: Sequence[str], paths: Sequence[str]
) -> SelectedLocations:
    """`read_rules` に渡された場所とパスから、索引に載ったルールの場所だけを選ぶ。"""
    listed = rule_locations(entries)
    targets: list[str] = []
    rejected: list[RejectedLocation] = []
    # 場所で引く: 相対パスは解かず、索引に載ったルールの場所だけを読む
    for location in locations:
        if not _is_absolute_location(location):
            rejected.append(RejectedLocation(location=location, reason=RELATIVE_LOCATION_REASON))
            continue
        resolved = resolve_location(location, Path(os.sep))
        if resolved in listed:
            targets.append(resolved)
        else:
            rejected.append(RejectedLocation(location=resolved, reason=NOT_IN_INDEX_REASON))
    # 対象のパスで引く: 絶対パスだけを、読む操作として当たるルールの場所へ引く
    for path in paths:
        if not os.path.isabs(path):
            rejected.append(RejectedLocation(location=path, reason=RELATIVE_PATH_REASON))
            continue
        resolved = resolve_location(path, Path(os.sep))
        targets.extend(rule.location for rule in match_path(entries, resolved, "read"))
    # 重なりは 1 つにする（並びは保つ）
    return SelectedLocations(targets=tuple(dict.fromkeys(targets)), rejected=tuple(rejected))
