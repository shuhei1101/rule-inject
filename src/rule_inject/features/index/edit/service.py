"""索引のエントリの書き込み・削除と、ファイルの置き換え。"""

from __future__ import annotations

import difflib
import io
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError
from ruamel.yaml.util import load_yaml_guess_indent

from rule_inject.features.index import entry_revs
from rule_inject.features.index.edit._yaml import round_trip_yaml, to_yaml_value
from rule_inject.features.index.edit.types import CheckChange, EditResult, IndexLocks
from rule_inject.shared.errors import IndexEditError, describe

RULES_KEY = "rules"
COMMENT_MARK = "#"
# 新規作成するエントリにキーを書く順（ここに無いキーは渡された順で後ろに置く）
ENTRY_KEY_ORDER = ("rule", "paths", "exclude", "tools", "args", "on", "read_by", "enabled")
# 改行
LF = "\n"
CRLF = "\r\n"
# `YAML.indent()` が受け付ける字下げの下限（マップの字下げと、リストの字下げ - 記号の字下げ）
MIN_MAPPING_INDENT = 1
MIN_SEQUENCE_ITEM_WIDTH = 2
# 差分に添える前後の行数
DIFF_CONTEXT_LINES = 3
# 一覧を取り直してから呼び直してもらうための案内
RELIST_HINT = "list_rules を取り直してから呼び直してください"


def _read_text(index_path: str) -> tuple[str, str]:
    """索引を UTF-8 で改行を変えずに読み、最初の改行が `\\r\\n` ならそれを控えて全て `\\n` にそろえる。内容と控えた改行を返す。"""
    try:
        text = Path(index_path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise IndexEditError(path=index_path, reason=describe(exc)) from exc
    first_break = text.find("\n")
    if first_break > 0 and text[first_break - 1] == "\r":
        return text.replace(CRLF, LF), CRLF
    return text, LF


def _index_yaml(index_path: str, text: str) -> YAML:
    """索引の字下げを推定し、それに合わせた round-trip の `YAML` を作る。推定できなければ既定の字下げにする。"""
    try:
        _, indent, sequence_indent = load_yaml_guess_indent(text)
    except YAMLError as exc:
        raise IndexEditError(
            path=index_path, reason=f"YAML として読めない: {describe(exc)}"
        ) from exc
    # マップとリストの字下げが推定でき、`indent()` が受け付ける範囲のときだけ使う
    if (
        indent is None
        or sequence_indent is None
        or indent - sequence_indent < MIN_MAPPING_INDENT
        or indent < sequence_indent + MIN_SEQUENCE_ITEM_WIDTH
    ):
        return round_trip_yaml()
    return round_trip_yaml(
        mapping=indent - sequence_indent, sequence=indent, offset=sequence_indent
    )


def _load(yaml: YAML, index_path: str, text: str) -> CommentedMap:
    """索引を round-trip で読む。YAML として読めない・最上位がマップでないときは IndexEditError を送出する。"""
    try:
        data = yaml.load(text)
    except YAMLError as exc:
        raise IndexEditError(
            path=index_path, reason=f"YAML として読めない: {describe(exc)}"
        ) from exc
    if not isinstance(data, CommentedMap):
        raise IndexEditError(path=index_path, reason="索引の最上位がマップでない")
    return data


def _dump(yaml: YAML, data: CommentedMap) -> str:
    """round-trip で読んだ内容を文字列へ書き出す。"""
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    return buffer.getvalue()


def _entries(index_path: str, data: CommentedMap) -> CommentedSeq:
    """`rules` のエントリのリストを返す。無いか値が空（None）なら空のリストを返す（`data` へは入れない）。"""
    rules = data.get(RULES_KEY)
    if rules is None:
        return CommentedSeq()
    if not isinstance(rules, CommentedSeq):
        raise IndexEditError(path=index_path, reason="rules がリストでない")
    return rules


def _check_target(index_path: str, text: str, rules: CommentedSeq, position: int, rev: str) -> None:
    """位置のエントリがあり、バージョンが合うことを確かめる。合わなければ IndexEditError を送出する。"""
    if position >= len(rules):
        raise IndexEditError(
            path=index_path,
            reason=f"位置 {position} のエントリが無い（索引のエントリは {len(rules)} 件）",
        )
    # バージョンは一覧・チェックと同じく、フックの読み取りで読んだエントリから求める
    try:
        current = entry_revs(text)[position]
    except ValueError as exc:
        raise IndexEditError(
            path=index_path,
            reason=(
                f"フックの読み取りが索引を読めず、バージョンを確かめられない: {exc}。"
                "索引を手で直してください"
            ),
        ) from exc
    if rev != current:
        raise IndexEditError(
            path=index_path,
            reason=f"expected_rev {rev} が今のバージョン {current} と違う。{RELIST_HINT}",
        )


def _unified_diff(index_path: str, before: str, after: str) -> str:
    """書く前と書いた後の unified diff（前後 3 行、ファイル名は索引のファイル名）を作る。"""
    name = Path(index_path).name
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=name,
            tofile=name,
            n=DIFF_CONTEXT_LINES,
        )
    )


def _replace_file(index_path: str, text: str) -> None:
    """同じフォルダの一時ファイルに書き、索引と置き換える。失敗したら一時ファイルを消して IndexEditError を送出する。"""
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=Path(index_path).parent, delete=False
        ) as temp:
            temp_path = temp.name
            temp.write(text)
            temp.flush()
            os.fsync(temp.fileno())
        # 索引のパーミッションを一時ファイルへ写してから置き換える
        shutil.copymode(index_path, temp_path)
        os.replace(temp_path, index_path)
    except OSError as exc:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
        raise IndexEditError(path=index_path, reason=describe(exc)) from exc


def _new_entry(entry: Mapping[str, Any]) -> CommentedMap:
    """新規作成するエントリを、キーの並びと値の書式を決めて作る。"""
    mapping = CommentedMap()
    ordered = [key for key in ENTRY_KEY_ORDER if key in entry]
    ordered.extend(key for key in entry if key not in ENTRY_KEY_ORDER)
    for key in ordered:
        mapping[key] = to_yaml_value(key, entry[key])
    return mapping


def _outside_lines(lines: Sequence[str], line_range: tuple[int, int] | None) -> list[str]:
    """対象の範囲（始まりと終わり。終わりを含む）の行を除いた行の並びを返す。範囲が無ければ全ての行を返す。"""
    if line_range is None:
        return list(lines)
    begin, end = line_range
    return [*lines[:begin], *lines[end + 1 :]]


def _check_layout(
    index_path: str,
    before_lines: Sequence[str],
    before_range: tuple[int, int] | None,
    after_lines: Sequence[str],
    after_range: tuple[int, int],
) -> None:
    """書く前と書いた後で、対象のエントリの外の行が変わらないことを確かめる。変われば IndexEditError を送出する。"""
    before_outside = _outside_lines(before_lines, before_range)
    after_outside = _outside_lines(after_lines, after_range)
    if before_outside == after_outside:
        return
    # 最初に違った行を、書く前の内容での行の番号（`parse_index` と同じ 1 始まり）にして知らせる
    first_diff = next(
        (
            number
            for number, (before, after) in enumerate(
                zip(before_outside, after_outside, strict=False)
            )
            if before != after
        ),
        min(len(before_outside), len(after_outside)),
    )
    skipped = (
        before_range[1] - before_range[0] + 1
        if before_range is not None and first_diff >= before_range[0]
        else 0
    )
    raise IndexEditError(
        path=index_path,
        reason=(
            "索引の書式を保って書けない"
            f"（対象のエントリの外の {first_diff + skipped + 1}行目が変わる）。索引を手で直してください"
        ),
    )


def write_entry(
    index_path: str,
    entry: Mapping[str, Any],
    *,
    position: int | None,
    expected_rev: str | None,
    remove_keys: Sequence[str],
    dry_run: bool,
    locks: IndexLocks,
    check_change: CheckChange,
) -> EditResult:
    """エントリを末尾へ新規作成するか、位置で指したエントリのキーを書き換える。新しい問題が出るときは書き込まない。"""
    # 同じ索引への書き込み・削除は 1 つずつ行う
    with locks.lock_for(index_path):
        before, newline = _read_text(index_path)
        yaml = _index_yaml(index_path, before)
        data = _load(yaml, index_path, before)
        # 書式を保てたかの確認に使う、書く前の内容の行の範囲は、書き換える前に求める
        before_data = _load(round_trip_yaml(), index_path, before)
        before_lines = before.splitlines()
        rules = _entries(index_path, data)
        # `rules` が無いか、値が空（None）か空のフロー形式のリストのときは、ブロックのリストを作る
        rules_created = position is None and (
            data.get(RULES_KEY) is None or (isinstance(rules, CommentedSeq) and not rules)
        )
        before_range: tuple[int, int] | None = None
        if position is None:
            if rules_created:
                data[RULES_KEY] = rules
                # 書く前の内容に `rules` のキーの行があれば、その行も対象の範囲に含める
                if RULES_KEY in before_data:
                    key_line = before_data.lc.key(RULES_KEY)[0]
                    before_range = (key_line, key_line)
            rules.fa.set_block_style()
            written_position = len(rules)
            rules.append(_new_entry(entry))
        else:
            _check_target(index_path, before, rules, position, expected_rev or "")
            written_position = position
            target = rules[position]
            # 渡されたキーは、あればその場で、無ければ末尾に書く。`remove_keys` のキーは削除する
            for key, value in entry.items():
                target[key] = to_yaml_value(key, value)
            for key in remove_keys:
                target.pop(key, None)
            before_range = _entry_line_range(before_lines, before_data, position)
        after = _dump(yaml, data)
        # 書式を保てたかを確かめる。書いたエントリの外の行が変わるときは書き込まない
        after_lines = after.splitlines()
        after_data = _load(round_trip_yaml(), index_path, after)
        after_range = _entry_line_range(after_lines, after_data, written_position)
        if rules_created:
            after_range = (after_data.lc.key(RULES_KEY)[0], after_range[1])
        elif position is None:
            # 新規作成したエントリは、直前のコメントを含めない（前のエントリの後ろのコメントは、書く前から外の行）
            entry_start = after_data[RULES_KEY].lc.item(written_position)[0]
            after_range = (entry_start, after_range[1])
        _check_layout(index_path, before_lines, before_range, after_lines, after_range)
        # 書いた後の索引がフックの読み取りで読めないときは、バージョンを持たせない（チェックが理由を返す）
        try:
            rev: str | None = entry_revs(after)[written_position]
        except ValueError:
            rev = None
        problems = check_change(index_path, before, after, rev)
        if problems:
            lines = "\n".join(problems)
            raise IndexEditError(
                path=index_path, reason=f"書いた後の索引がチェックに通らない:\n{lines}"
            )
        diff = _unified_diff(index_path, before, after)
        if not dry_run:
            _replace_file(index_path, after.replace(LF, newline))
        return EditResult(
            index=index_path,
            position=written_position,
            rev=rev,
            rule=None,
            written=not dry_run,
            diff=diff,
        )


def _is_content_line(line: str) -> bool:
    """空行とコメントだけの行でない（内容のある）行か。"""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith(COMMENT_MARK)


def _last_content_line(lines: Sequence[str], start: int, boundary: int) -> int:
    """`start` から `boundary` の手前までで、空行とコメントだけの行を除いた最後の行の番号を返す。"""
    for number in range(boundary - 1, start - 1, -1):
        if _is_content_line(lines[number]):
            return number
    return start


def _entry_line_range(lines: Sequence[str], data: CommentedMap, position: int) -> tuple[int, int]:
    """削除するエントリの行の範囲（始まりと終わり。終わりを含む。行の番号は 0 始まり）を返す。"""
    rules = data[RULES_KEY]
    starts = [rules.lc.item(number)[0] for number in range(len(rules))]
    keys = list(data.keys())
    following = keys[keys.index(RULES_KEY) + 1 :]
    # 最後のエントリの終わりの境界は、`rules` の次の最上位のキーの行かファイルの終わり
    after_rules = data.lc.key(following[0])[0] if following else len(lines)

    def last_line(number: int) -> int:
        """エントリ `number` の最後の内容の行を返す。"""
        boundary = starts[number + 1] if number + 1 < len(starts) else after_rules
        return _last_content_line(lines, starts[number], boundary)

    # 始まりは、1 つ前のエントリの最後の内容の次の行（先頭なら `rules` のキーの次の行）
    begin = data.lc.key(RULES_KEY)[0] + 1 if position == 0 else last_line(position - 1) + 1
    return begin, last_line(position)


def delete_entry(
    index_path: str,
    *,
    position: int,
    expected_rev: str,
    dry_run: bool,
    locks: IndexLocks,
) -> EditResult:
    """位置で指したエントリを、そのエントリに付いたコメントとともに削除する。"""
    with locks.lock_for(index_path):
        before, newline = _read_text(index_path)
        data = _load(round_trip_yaml(), index_path, before)
        rules = _entries(index_path, data)
        _check_target(index_path, before, rules, position, expected_rev)
        rule = str(rules[position]["rule"])
        # 対象のエントリの行だけを除く（前のエントリの行末のコメントと、次のエントリの直前のコメントは残す）
        lines = before.splitlines(keepends=True)
        begin, end = _entry_line_range(lines, data, position)
        after = "".join(lines[:begin] + lines[end + 1 :])
        diff = _unified_diff(index_path, before, after)
        if not dry_run:
            _replace_file(index_path, after.replace(LF, newline))
        return EditResult(
            index=index_path,
            position=position,
            rev=None,
            rule=rule,
            written=not dry_run,
            diff=diff,
        )
