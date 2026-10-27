"""設定ファイルと索引の YAML に共通の、行・文字列・リストの読み取り（標準ライブラリだけ）。"""

from __future__ import annotations

from dataclasses import dataclass

LIST_ITEM_MARK = "- "
QUOTE_CHARS = "\"'"
# 開き引用符と閉じ引用符で最低でも 2 字になる
MIN_QUOTED_LENGTH = 2
# 引用符なしの値の先頭に置けない、YAML では別の意味になる文字
RESERVED_HEADS = "{|>&!%@`*"


@dataclass(frozen=True, slots=True, kw_only=True)
class Line:
    """コメントと空行を落とした後の 1 行。"""

    number: int
    indent: int
    text: str


def yaml_error(number: int, reason: str) -> ValueError:
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


def tokenize(text: str) -> list[Line]:
    """コメントと空行を落とし、行番号とインデントを持つ行にする。"""
    lines: list[Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        body = _strip_comment(raw).rstrip()
        if not body.strip():
            continue
        content = body.lstrip()
        if "\t" in body[: len(body) - len(content)]:
            raise yaml_error(number, "インデントにタブは使えません")
        lines.append(Line(number=number, indent=len(body) - len(content), text=content))
    return lines


def parse_scalar(text: str, number: int) -> str:
    """引用符あり・なしの文字列 1 つを読む。"""
    text = text.strip()
    if not text:
        raise yaml_error(number, "値が空です")
    # 引用符あり: 閉じ引用符が末尾にあることを確かめる
    if text[0] in QUOTE_CHARS:
        quote = text[0]
        if len(text) < MIN_QUOTED_LENGTH or text[-1] != quote:
            raise yaml_error(number, "引用符が閉じていません")
        inner = text[1:-1]
        if quote == "'":
            return inner.replace("''", "'")
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    # 引用符なし: YAML では別の意味になる先頭の文字は引用符で囲ませる
    if text[0] in RESERVED_HEADS:
        raise yaml_error(number, f"先頭が {text[0]} の値は引用符で囲んでください")
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
        raise yaml_error(number, "引用符が閉じていません")
    items.append("".join(current))
    return items


def parse_flow_list(text: str, number: int) -> list[str]:
    """`[a, b]` の形式のリストを読む。"""
    if not text.endswith("]"):
        raise yaml_error(number, "リストが `]` で閉じていません")
    body = text[1:-1]
    if not body.strip():
        return []
    return [parse_scalar(item, number) for item in _split_flow_items(body, number)]


def read_block_list(lines: list[Line], start: int, min_indent: int) -> tuple[list[str], int]:
    """`- a` の行が続く限りブロックのリストを読み、次に読む行の位置を返す。"""
    items: list[str] = []
    position = start
    while position < len(lines):
        line = lines[position]
        if line.indent < min_indent or not line.text.startswith(LIST_ITEM_MARK):
            break
        items.append(parse_scalar(line.text[len(LIST_ITEM_MARK) :], line.number))
        position += 1
    return items, position


def split_key(line: Line) -> tuple[str, str]:
    """`key: value` の行をキーと値に分ける。"""
    key, separator, rest = line.text.partition(":")
    if not separator or not key.strip() or " " in key.strip():
        raise yaml_error(line.number, "`キー: 値` の形式で書いてください")
    return key.strip(), rest


def read_value(
    lines: list[Line], line: Line, next_position: int, key: str, rest: str, min_indent: int
) -> tuple[str | list[str], int]:
    """キーの値を読み、次に読む行の位置を返す。値が無ければ続く行のブロックのリストを読む。"""
    rest = rest.strip()
    # 同じ行に値がある: フローのリストか文字列
    if rest.startswith("["):
        return parse_flow_list(rest, line.number), next_position
    if rest:
        return parse_scalar(rest, line.number), next_position
    # 同じ行に値が無い: 続く行のブロックのリスト
    items, position = read_block_list(lines, next_position, min_indent)
    if not items:
        raise yaml_error(line.number, f"{key} の値がありません")
    return items, position
