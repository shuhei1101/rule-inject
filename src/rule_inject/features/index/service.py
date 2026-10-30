"""索引の読み込みと、パス・ツール名の照合。"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from rule_inject.features.index._yaml import ENABLED_KEY, parse_index
from rule_inject.features.index.types import (
    DEFAULT_ON,
    ArgCondition,
    EntryOutcome,
    IndexContent,
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

NAME_SEPARATOR = "、"
# 先頭がこの文字列のパターンは、残りを正規表現として読む
REGEX_PREFIX = "re:"
# 引数のキーをオブジェクトの子へたどる区切り
ARG_KEY_SEPARATOR = "."
# 条件の木で中へたどる束のキー。`not` はたどらない
TREE_GROUP_KEYS = ("and", "or")
# 条件の木の条件のうち、`values` を照合する値にしない `op`（その値の文書を読まない検索のため）
NEGATED_OPS = frozenset({"ne", "not_contains", "not_exists"})
# Read で読めないため読み飛ばす `rule` の頭
URL_SCHEMES = ("http://", "https://")
# エントリを照合に使わない `enabled` の値
DISABLED_VALUE = "false"
# エントリのバージョンに使う SHA-256 の 16 進の先頭の字数
REV_LENGTH = 12


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


def entry_rev(raw: Mapping[str, Any]) -> str:
    """エントリのキーと値から、書式によらないバージョンを求める。"""
    # キーの順に並べた JSON の SHA-256 の先頭を使う（コメント・引用符・字下げは入らない）
    canonical = json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:REV_LENGTH]


def entry_revs(text: str) -> tuple[str, ...]:
    """索引の内容から、エントリごとのバージョンを位置の順に返す。読めなければ ValueError を送出する。"""
    return tuple(entry_rev(raw) for raw in parse_index(text)[1])


def _outcome(
    position: int,
    raw: Mapping[str, Any],
    *,
    index_dir: Path,
    env: Mapping[str, str],
    fallback_on: frozenset[Operation],
) -> EntryOutcome:
    """エントリ 1 つを、無効・読み飛ばし・有効のどれかにして返す。"""
    rev = entry_rev(raw)
    # 無効のエントリは照合に使わないため、展開・解決・コンパイルの前に外して理由も残さない
    if raw.get(ENABLED_KEY) == DISABLED_VALUE:
        return EntryOutcome(
            position=position, raw=raw, rev=rev, status="disabled", entry=None, reason=None
        )

    def skipped(reason: str) -> EntryOutcome:
        """読み飛ばしたエントリの結果を、理由つきで作る。"""
        return EntryOutcome(
            position=position, raw=raw, rev=rev, status="skipped", entry=None, reason=reason
        )

    # `rule` の変数参照を展開する。展開できない名前が残ったエントリは読み飛ばして理由を残す
    written_rule = str(raw["rule"])
    expansion = expand_variables(written_rule, env)
    if expansion.unresolved:
        names = NAME_SEPARATOR.join(expansion.unresolved)
        return skipped(f"rule {written_rule} の変数参照を展開できない: {names}")
    # URL の `rule` は Read で読めないため、読み飛ばして理由を残す
    if expansion.text.startswith(URL_SCHEMES):
        return skipped(f"rule {expansion.text} は URL のため Read で読めない")
    # 展開した `rule` を索引のフォルダから解き、`on` が無ければ索引の既定で埋める。
    # 読めない正規表現を持つエントリは読み飛ばして理由を残す
    try:
        entry = _build_entry(raw, resolve_location(expansion.text, index_dir), fallback_on)
    except IndexReadError as exc:
        return skipped(exc.reason)
    return EntryOutcome(
        position=position, raw=raw, rev=rev, status="effective", entry=entry, reason=None
    )


def read_index_text(index_path: str, text: str, env: Mapping[str, str]) -> IndexContent:
    """索引の内容を読み、エントリごとの位置・バージョン・照合に使うかを返す。読めなければ IndexReadError を送出する。"""
    try:
        default_on, raw_entries = parse_index(text)
    except ValueError as exc:
        raise IndexReadError(path=index_path, reason=describe(exc)) from exc
    fallback_on = frozenset(default_on or DEFAULT_ON)
    index_dir = Path(index_path).parent
    outcomes = tuple(
        _outcome(position, raw, index_dir=index_dir, env=env, fallback_on=fallback_on)
        for position, raw in enumerate(raw_entries)
    )
    return IndexContent(path=index_path, outcomes=outcomes)


def read_index(index_path: str, env: Mapping[str, str]) -> IndexContent:
    """索引 1 つを読み、エントリごとの位置・バージョン・照合に使うかを返す。読めなければ IndexReadError を送出する。"""
    try:
        text = Path(index_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise IndexReadError(path=index_path, reason=describe(exc)) from exc
    return read_index_text(index_path, text, env)


def load_indexes(index_paths: Sequence[str], env: Mapping[str, str]) -> IndexLoadResult:
    """設定が決めた索引を渡された順に読み、読めたエントリと読めなかった索引・読み飛ばしたエントリを返す。"""
    entries: list[IndexEntry] = []
    failures: list[IndexReadError] = []
    for index_path in index_paths:
        # 読めない索引は集めて、次の索引へ進む
        try:
            content = read_index(index_path, env)
        except IndexReadError as exc:
            failures.append(exc)
            continue
        # 有効なエントリは照合に使い、読み飛ばしたエントリは理由を残す（無効のエントリはどちらにも入れない）
        for outcome in content.outcomes:
            if outcome.status == "effective" and outcome.entry is not None:
                entries.append(outcome.entry)
            elif outcome.status == "skipped":
                failures.append(IndexReadError(path=content.path, reason=outcome.reason or ""))
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


def _tree_values(node: Any, field: str) -> list[Any]:
    """条件の木を `and`・`or` の入れ子までたどり、`field` が一致する条件の `values` をつないで返す。木として読めなければ空。"""
    if not isinstance(node, Mapping):
        return []
    values: list[Any] = []
    # 束は、中の節を深さを問わずたどる（`not` の中はたどらない）
    for group_key in TREE_GROUP_KEYS:
        children = node.get(group_key)
        if isinstance(children, list):
            for child in children:
                values.extend(_tree_values(child, field))
    # 条件は、`field` が一致し、否定の `op` でないときだけ `values` を取る
    if node.get("field") == field and node.get("op") not in NEGATED_OPS and "values" in node:
        condition_values = node["values"]
        if isinstance(condition_values, list):
            values.extend(condition_values)
        else:
            values.append(condition_values)
    return values


def _argument_values(
    tool_input: Mapping[str, Any], path: str, field: str | None = None
) -> list[str]:
    """ドット区切りの道筋が指す引数の値を、`field` があれば条件の木として読んだ値を、照合する文字列の並びにする。道筋が無ければ空。"""
    nodes: list[Any] = [tool_input]
    # 先頭から順にたどる。途中の配列は要素ごとにたどり、オブジェクトでない値と無いキーは捨てる
    for part in path.split(ARG_KEY_SEPARATOR):
        nodes = [
            node[part]
            for node in _expand_arrays(nodes)
            if isinstance(node, Mapping) and part in node
        ]
    # `field` があれば、たどり着いた値（配列は要素ごと）を条件の木の値に置き換える
    if field is not None:
        nodes = [value for node in _expand_arrays(nodes) for value in _tree_values(node, field)]
    values: list[str] = []
    for node in _expand_arrays(nodes):
        # 文字列はそのまま、文字列以外のスカラーは JSON の表記にし、オブジェクトと配列は捨てる
        if isinstance(node, str):
            values.append(node)
        elif not isinstance(node, Mapping | list):
            values.append(json.dumps(node))
    return values


def match_arg_pattern(pattern: MatchPattern, value: str) -> bool:
    """引数の値 1 つにパターンを当てる（正規表現は部分一致、glob は `fnmatch.fnmatchcase`）。"""
    return _match_pattern(pattern, value, glob_match=_fnmatch_glob)


def _match_args(conditions: Sequence[ArgCondition], tool_input: Mapping[str, Any]) -> bool:
    """全てのキーについて、値のどれかがパターンのどれかに当たるか。値が 1 つも無いキーは当たらない。"""
    return all(
        any(
            match_arg_pattern(pattern, value)
            for value in _argument_values(tool_input, condition.path, condition.field)
            for pattern in condition.patterns
        )
        for condition in conditions
    )


def entry_matches_path(entry: IndexEntry, path: str) -> bool:
    """エントリ 1 件が対象の絶対パスに当たるかを返す。`paths` のどれかに当たり、`exclude` のどれにも当たらなければ当たる。"""
    return any(
        _match_pattern(pattern, path, glob_match=_glob_match) for pattern in entry.paths
    ) and not any(
        _match_pattern(pattern, path, glob_match=_glob_match) for pattern in entry.exclude
    )


def match_path(entries: Sequence[IndexEntry], path: str, operation: Operation) -> list[MatchedRule]:
    """対象のパスに当たるエントリをルールごとに 1 件へまとめる。"""
    matched = [entry for entry in entries if entry_matches_path(entry, path)]
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
