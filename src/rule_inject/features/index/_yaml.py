"""索引の YAML のうち、設定の設計書に挙げたキーと形式だけを標準ライブラリで読む。"""

from __future__ import annotations

from rule_inject.features.index.types import OPERATIONS, Operation
from rule_inject.shared.yaml_lines import (
    LIST_ITEM_MARK,
    Line,
    read_value,
    split_key,
    tokenize,
    yaml_error,
)

TOP_KEYS = ("default_on", "rules")
ENTRY_KEYS = ("rule", "paths", "exclude", "tools", "args", "on", "read_by")
# 値がリストのエントリのキー（`rule` だけが文字列、`args` はキーごとのリストのマップ、`read_by` はマップのリスト）
LIST_ENTRY_KEYS = ("paths", "exclude", "tools", "on")
ARGS_KEY = "args"
READ_BY_KEY = "read_by"
# `read_by` の要素のキー（`tools` は必須）
READ_BY_KEYS = ("tools", ARGS_KEY)
READ_BY_TOOLS_KEY = "tools"

type ReadByItem = dict[str, list[str] | dict[str, list[str]]]
type Value = str | list[str] | dict[str, list[str]] | list[ReadByItem]


def _parse_operations(values: list[str], number: int) -> tuple[Operation, ...]:
    """`on` と `default_on` の値を、許す操作の種別だけにして返す。"""
    for value in values:
        if value not in OPERATIONS:
            raise yaml_error(number, f"操作の種別は {', '.join(OPERATIONS)} のどれかです: {value}")
    return tuple(operation for operation in OPERATIONS if operation in values)


def _read_args(
    lines: list[Line], line: Line, next_position: int, rest: str, key_indent: int
) -> tuple[dict[str, list[str]], int]:
    """`args` の続く行に並ぶ `キー: リスト` のブロックのマップを読み、次に読む行の位置を返す。"""
    # 同じ行に値がある（フローのマップなど）形式は読まない
    if rest.strip():
        raise yaml_error(line.number, "args は続く行に `キー:` とパターンのリストを並べてください")
    if next_position >= len(lines) or lines[next_position].indent <= key_indent:
        raise yaml_error(line.number, "args の値がありません")
    # 続く行の最初のキーの桁に、残りのキーが揃う
    arg_indent = lines[next_position].indent
    args: dict[str, list[str]] = {}
    position = next_position
    while position < len(lines) and lines[position].indent > key_indent:
        arg_line = lines[position]
        if arg_line.indent != arg_indent:
            raise yaml_error(arg_line.number, "args のキーは同じ桁に揃えてください")
        arg_key, arg_rest = split_key(arg_line)
        if arg_key in args:
            raise yaml_error(arg_line.number, f"args のキーが重複しています: {arg_key}")
        value, position = read_value(lines, arg_line, position + 1, arg_key, arg_rest, arg_indent)
        if not isinstance(value, list):
            raise yaml_error(arg_line.number, f"args の {arg_key} はリストで書いてください")
        args[arg_key] = value
    return args, position


def _read_read_by_item(lines: list[Line], position: int) -> tuple[ReadByItem, int]:
    """`read_by` の `- ` で始まる要素 1 つ（`tools` と任意の `args`）を読み、次に読む行の位置を返す。"""
    first = lines[position]
    after_mark = first.text[len(LIST_ITEM_MARK) :]
    content = after_mark.lstrip(" ")
    # `- ` の後ろのキーの桁に、続くキーが揃う
    key_indent = first.indent + len(LIST_ITEM_MARK) + len(after_mark) - len(content)
    current = Line(number=first.number, indent=key_indent, text=content)
    item: ReadByItem = {}
    while True:
        key, rest = split_key(current)
        if key not in READ_BY_KEYS:
            raise yaml_error(current.number, f"read_by の要素に許さないキーです: {key}")
        if key in item:
            raise yaml_error(current.number, f"read_by の要素のキーが重複しています: {key}")
        # args はエントリの args と同じブロックのマップ、tools はリスト
        if key == ARGS_KEY:
            item[key], position = _read_args(lines, current, position + 1, rest, key_indent)
        else:
            value, position = read_value(lines, current, position + 1, key, rest, key_indent)
            if not isinstance(value, list):
                raise yaml_error(current.number, f"read_by の {key} はリストで書いてください")
            item[key] = value
        # 次の行が同じ桁のキーなら、同じ要素の続き
        if position >= len(lines) or lines[position].indent != key_indent:
            break
        current = lines[position]
    if READ_BY_TOOLS_KEY not in item:
        raise yaml_error(first.number, "read_by の要素に tools がありません")
    return item, position


def _read_read_by(
    lines: list[Line], line: Line, next_position: int, rest: str, key_indent: int
) -> tuple[list[ReadByItem], int]:
    """`read_by` の続く行に並ぶ `- ` で始まる要素のブロックのリストを読み、次に読む行の位置を返す。"""
    # 同じ行に値がある（フローのリストなど）形式は読まない
    if rest.strip():
        raise yaml_error(line.number, "read_by は続く行に `- ` で始まるマップを並べてください")
    items: list[ReadByItem] = []
    position = next_position
    while (
        position < len(lines)
        and lines[position].indent >= key_indent
        and lines[position].text.startswith(LIST_ITEM_MARK)
    ):
        item, position = _read_read_by_item(lines, position)
        items.append(item)
    if not items:
        raise yaml_error(line.number, "read_by の値がありません")
    return items, position


def _read_entry(lines: list[Line], position: int) -> tuple[dict[str, Value], int]:
    """`- ` で始まるエントリ 1 つを読み、次に読む行の位置を返す。"""
    first = lines[position]
    after_mark = first.text[len(LIST_ITEM_MARK) :]
    content = after_mark.lstrip(" ")
    # `- ` の後ろのキーの桁に、続くキーが揃う
    key_indent = first.indent + len(LIST_ITEM_MARK) + len(after_mark) - len(content)
    current = Line(number=first.number, indent=key_indent, text=content)
    entry: dict[str, Value] = {}
    while True:
        key, rest = split_key(current)
        if key not in ENTRY_KEYS:
            raise yaml_error(current.number, f"許さないキーです: {key}")
        if key in entry:
            raise yaml_error(current.number, f"キーが重複しています: {key}")
        # args はキーごとのパターンのリストを並べたマップ、read_by は要素のリスト、それ以外は文字列かリスト
        if key == ARGS_KEY:
            entry[key], position = _read_args(lines, current, position + 1, rest, key_indent)
        elif key == READ_BY_KEY:
            entry[key], position = _read_read_by(lines, current, position + 1, rest, key_indent)
        else:
            entry[key], position = read_value(lines, current, position + 1, key, rest, key_indent)
        # 次の行が同じ桁のキーなら、同じエントリの続き
        if position >= len(lines) or lines[position].indent != key_indent:
            return entry, position
        current = lines[position]


def _validate_entry(entry: dict[str, Value], number: int) -> None:
    """エントリの `rule` の有無と各キーの値の形式を確かめる。"""
    if "rule" not in entry:
        raise yaml_error(number, "エントリに rule がありません")
    if not isinstance(entry["rule"], str):
        raise yaml_error(number, "rule は文字列で書いてください")
    for key in LIST_ENTRY_KEYS:
        if key in entry and not isinstance(entry[key], list):
            raise yaml_error(number, f"{key} はリストで書いてください")
    if "on" in entry:
        _parse_operations(list(entry["on"]), number)


def parse_index(text: str) -> tuple[tuple[Operation, ...] | None, list[dict[str, Value]]]:
    """索引の YAML から `default_on`（無ければ None）と `rules` の各エントリのキーと値を返す。"""
    lines = tokenize(text)
    default_on: tuple[Operation, ...] | None = None
    entries: list[dict[str, Value]] = []
    position = 0
    while position < len(lines):
        line = lines[position]
        if line.indent != 0:
            raise yaml_error(line.number, "最上位のキーはインデントなしで書いてください")
        key, rest = split_key(line)
        if key not in TOP_KEYS:
            raise yaml_error(line.number, f"許さないキーです: {key}")
        # default_on: 操作の種別のリスト
        if key == "default_on":
            value, position = read_value(lines, line, position + 1, key, rest, 0)
            if not isinstance(value, list):
                raise yaml_error(line.number, "default_on はリストで書いてください")
            default_on = _parse_operations(value, line.number)
            continue
        # rules: 空のリストか、`- ` で始まるエントリの並び
        if rest.strip() and rest.strip() != "[]":
            raise yaml_error(line.number, "rules はエントリを `- ` で並べてください")
        position += 1
        while position < len(lines) and lines[position].text.startswith(LIST_ITEM_MARK):
            entry_number = lines[position].number
            entry, position = _read_entry(lines, position)
            _validate_entry(entry, entry_number)
            entries.append(entry)
    return default_on, entries
