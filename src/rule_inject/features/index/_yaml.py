"""索引の YAML のうち、設定の設計書に挙げたキーと形だけを標準ライブラリで読む。"""

from __future__ import annotations

from dataclasses import dataclass

from rule_inject.features.index.types import OPERATIONS, Operation

TOP_KEYS = ("default_on", "rules")
ENTRY_KEYS = ("rule", "paths", "exclude", "tools", "args", "on")
# 値がリストのエントリのキー（`rule` だけが文字列、`args` はキーごとのリストのマップ）
LIST_ENTRY_KEYS = ("paths", "exclude", "tools", "on")
ARGS_KEY = "args"
LIST_ITEM_MARK = "- "
QUOTE_CHARS = "\"'"
# 開き引用符と閉じ引用符で最低でも 2 字になる
MIN_QUOTED_LENGTH = 2
# 引用符なしの値の先頭に置けない、YAML では別の意味になる文字
RESERVED_HEADS = "{|>&!%@`*"

type Value = str | list[str] | dict[str, list[str]]


@dataclass(frozen=True, slots=True, kw_only=True)
class _Line:
    """コメントと空行を落とした後の 1 行。"""

    number: int
    indent: int
    text: str


def _error(number: int, reason: str) -> ValueError:
    """行番号つきの ValueError を作る。"""
    return ValueError(f"{number}行目: {reason}")


def _strip_comment(raw: str) -> str:
    """引用符の外の `#`（行頭か空白の直後）から行末までを落とす。"""
    quote = ""
    for position, char in enumerate(raw):
        if quote:
            # 引用符の中は閉じるまで読み進める
            if char == quote:
                quote = ""
        elif char in QUOTE_CHARS:
            quote = char
        elif char == "#" and (position == 0 or raw[position - 1] in " \t"):
            return raw[:position]
    return raw


def _tokenize(text: str) -> list[_Line]:
    """コメントと空行を落とし、行番号とインデントを持つ行にする。"""
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        body = _strip_comment(raw).rstrip()
        if not body.strip():
            continue
        content = body.lstrip()
        if "\t" in body[: len(body) - len(content)]:
            raise _error(number, "インデントにタブは使えません")
        lines.append(_Line(number=number, indent=len(body) - len(content), text=content))
    return lines


def _parse_scalar(text: str, number: int) -> str:
    """引用符あり・なしの文字列 1 つを読む。"""
    text = text.strip()
    if not text:
        raise _error(number, "値が空です")
    # 引用符あり: 閉じ引用符が末尾にあることを確かめる
    if text[0] in QUOTE_CHARS:
        quote = text[0]
        if len(text) < MIN_QUOTED_LENGTH or text[-1] != quote:
            raise _error(number, "引用符が閉じていません")
        inner = text[1:-1]
        if quote == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    # 引用符なし: YAML では別の意味になる先頭の文字は引用符で囲ませる
    if text[0] in RESERVED_HEADS:
        raise _error(number, f"先頭が {text[0]} の値は引用符で囲んでください")
    return text


def _split_flow_items(body: str, number: int) -> list[str]:
    """フローのリストの中身を、引用符の外のカンマで分ける。"""
    items: list[str] = []
    current: list[str] = []
    quote = ""
    for char in body:
        if quote:
            if char == quote:
                quote = ""
        elif char in QUOTE_CHARS:
            quote = char
        elif char == ",":
            items.append("".join(current))
            current = []
            continue
        current.append(char)
    if quote:
        raise _error(number, "引用符が閉じていません")
    items.append("".join(current))
    return items


def _parse_flow_list(text: str, number: int) -> list[str]:
    """`[a, b]` の形のリストを読む。"""
    if not text.endswith("]"):
        raise _error(number, "リストが `]` で閉じていません")
    body = text[1:-1]
    if not body.strip():
        return []
    return [_parse_scalar(item, number) for item in _split_flow_items(body, number)]


def _read_block_list(lines: list[_Line], start: int, min_indent: int) -> tuple[list[str], int]:
    """`- a` の行が続く限りブロックのリストを読み、次に読む行の位置を返す。"""
    items: list[str] = []
    position = start
    while position < len(lines):
        line = lines[position]
        if line.indent < min_indent or not line.text.startswith(LIST_ITEM_MARK):
            break
        items.append(_parse_scalar(line.text[len(LIST_ITEM_MARK) :], line.number))
        position += 1
    return items, position


def _split_key(line: _Line) -> tuple[str, str]:
    """`key: value` の行をキーと値に分ける。"""
    key, separator, rest = line.text.partition(":")
    if not separator or not key.strip() or " " in key.strip():
        raise _error(line.number, "`キー: 値` の形で書いてください")
    return key.strip(), rest


def _parse_operations(values: list[str], number: int) -> tuple[Operation, ...]:
    """`on` と `default_on` の値を、許す操作の種別だけにして返す。"""
    for value in values:
        if value not in OPERATIONS:
            raise _error(number, f"操作の種別は {', '.join(OPERATIONS)} のどれかです: {value}")
    return tuple(operation for operation in OPERATIONS if operation in values)


def _read_value(
    lines: list[_Line], line: _Line, next_position: int, key: str, rest: str, min_indent: int
) -> tuple[Value, int]:
    """キーの値を読み、次に読む行の位置を返す。値が無ければ続く行のブロックのリストを読む。"""
    rest = rest.strip()
    # 同じ行に値がある: フローのリストか文字列
    if rest.startswith("["):
        return _parse_flow_list(rest, line.number), next_position
    if rest:
        return _parse_scalar(rest, line.number), next_position
    # 同じ行に値が無い: 続く行のブロックのリスト
    items, position = _read_block_list(lines, next_position, min_indent)
    if not items:
        raise _error(line.number, f"{key} の値がありません")
    return items, position


def _read_args(
    lines: list[_Line], line: _Line, next_position: int, rest: str, key_indent: int
) -> tuple[dict[str, list[str]], int]:
    """`args` の続く行に並ぶ `キー: リスト` のブロックのマップを読み、次に読む行の位置を返す。"""
    # 同じ行に値がある（フローのマップなど）形は読まない
    if rest.strip():
        raise _error(line.number, "args は続く行に `キー:` とパターンのリストを並べてください")
    if next_position >= len(lines) or lines[next_position].indent <= key_indent:
        raise _error(line.number, "args の値がありません")
    # 続く行の最初のキーの桁に、残りのキーが揃う
    arg_indent = lines[next_position].indent
    args: dict[str, list[str]] = {}
    position = next_position
    while position < len(lines) and lines[position].indent > key_indent:
        arg_line = lines[position]
        if arg_line.indent != arg_indent:
            raise _error(arg_line.number, "args のキーは同じ桁に揃えてください")
        arg_key, arg_rest = _split_key(arg_line)
        if arg_key in args:
            raise _error(arg_line.number, f"args のキーが重複しています: {arg_key}")
        value, position = _read_value(lines, arg_line, position + 1, arg_key, arg_rest, arg_indent)
        if not isinstance(value, list):
            raise _error(arg_line.number, f"args の {arg_key} はリストで書いてください")
        args[arg_key] = value
    return args, position


def _read_entry(lines: list[_Line], position: int) -> tuple[dict[str, Value], int]:
    """`- ` で始まるエントリ 1 つを読み、次に読む行の位置を返す。"""
    first = lines[position]
    after_mark = first.text[len(LIST_ITEM_MARK) :]
    content = after_mark.lstrip(" ")
    # `- ` の後ろのキーの桁に、続くキーが揃う
    key_indent = first.indent + len(LIST_ITEM_MARK) + len(after_mark) - len(content)
    current = _Line(number=first.number, indent=key_indent, text=content)
    entry: dict[str, Value] = {}
    while True:
        key, rest = _split_key(current)
        if key not in ENTRY_KEYS:
            raise _error(current.number, f"許さないキーです: {key}")
        if key in entry:
            raise _error(current.number, f"キーが重複しています: {key}")
        # args はキーごとのパターンのリストを並べたマップ、それ以外は文字列かリスト
        if key == ARGS_KEY:
            entry[key], position = _read_args(lines, current, position + 1, rest, key_indent)
        else:
            entry[key], position = _read_value(lines, current, position + 1, key, rest, key_indent)
        # 次の行が同じ桁のキーなら、同じエントリの続き
        if position >= len(lines) or lines[position].indent != key_indent:
            return entry, position
        current = lines[position]


def _validate_entry(entry: dict[str, Value], number: int) -> None:
    """エントリの `rule` の有無と各キーの値の形を確かめる。"""
    if "rule" not in entry:
        raise _error(number, "エントリに rule がありません")
    if not isinstance(entry["rule"], str):
        raise _error(number, "rule は文字列で書いてください")
    for key in LIST_ENTRY_KEYS:
        if key in entry and not isinstance(entry[key], list):
            raise _error(number, f"{key} はリストで書いてください")
    if "on" in entry:
        _parse_operations(list(entry["on"]), number)


def parse_index(text: str) -> tuple[tuple[Operation, ...] | None, list[dict[str, Value]]]:
    """索引の YAML から `default_on`（無ければ None）と `rules` の各エントリのキーと値を返す。"""
    lines = _tokenize(text)
    default_on: tuple[Operation, ...] | None = None
    entries: list[dict[str, Value]] = []
    position = 0
    while position < len(lines):
        line = lines[position]
        if line.indent != 0:
            raise _error(line.number, "最上位のキーはインデントなしで書いてください")
        key, rest = _split_key(line)
        if key not in TOP_KEYS:
            raise _error(line.number, f"許さないキーです: {key}")
        # default_on: 操作の種別のリスト
        if key == "default_on":
            value, position = _read_value(lines, line, position + 1, key, rest, 0)
            if not isinstance(value, list):
                raise _error(line.number, "default_on はリストで書いてください")
            default_on = _parse_operations(value, line.number)
            continue
        # rules: 空のリストか、`- ` で始まるエントリの並び
        if rest.strip() and rest.strip() != "[]":
            raise _error(line.number, "rules はエントリを `- ` で並べてください")
        position += 1
        while position < len(lines) and lines[position].text.startswith(LIST_ITEM_MARK):
            entry_number = lines[position].number
            entry, position = _read_entry(lines, position)
            _validate_entry(entry, entry_number)
            entries.append(entry)
    return default_on, entries
