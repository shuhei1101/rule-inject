"""設定ファイルの YAML のうち、設定の設計書に挙げたキーと形式だけを標準ライブラリで読む。"""

from __future__ import annotations

from rule_inject.shared.yaml_lines import (
    LIST_ITEM_MARK,
    Line,
    read_value,
    split_key,
    tokenize,
    yaml_error,
)

GLOBAL_KEY = "global"
PROJECTS_KEY = "projects"
TOP_KEYS = (GLOBAL_KEY, PROJECTS_KEY)
# 値がリストのキーと、文字列のキー
GLOBAL_LIST_KEYS = ("indexes",)
GLOBAL_SCALAR_KEYS = ("state_dir", "log_dir", "record_retention_days", "log_retention_days")
PROJECT_LIST_KEYS = ("indexes",)
PROJECT_SCALAR_KEYS = ("match",)
EMPTY_LIST = "[]"

type Table = dict[str, str | list[str]]
type Settings = dict[str, Table | list[Table]]


def _check_value_type(
    key: str,
    value: str | list[str],
    line: Line,
    list_keys: tuple[str, ...],
    owner: str,
) -> None:
    """キーの値がリストか文字列かの形式を確かめる。"""
    if key in list_keys and not isinstance(value, list):
        raise yaml_error(line.number, f"{owner}の {key} はリストで書いてください")
    if key not in list_keys and isinstance(value, list):
        raise yaml_error(line.number, f"{owner}の {key} は文字列で書いてください")


def _read_global(lines: list[Line], line: Line, next_position: int, rest: str) -> tuple[Table, int]:
    """`global` の続く行に並ぶ `キー: 値` のブロックのマップを読み、次に読む行の位置を返す。"""
    # 同じ行に値がある（フローのマップなど）形式は読まない
    if rest.strip():
        raise yaml_error(line.number, "global は続く行に `キー: 値` を並べてください")
    if next_position >= len(lines) or lines[next_position].indent <= line.indent:
        raise yaml_error(line.number, "global の値がありません")
    # 続く行の最初のキーの桁に、残りのキーが揃う
    map_indent = lines[next_position].indent
    values: Table = {}
    position = next_position
    while position < len(lines) and lines[position].indent > line.indent:
        key_line = lines[position]
        if key_line.indent != map_indent:
            raise yaml_error(key_line.number, "global のキーは同じ桁に揃えてください")
        key, key_rest = split_key(key_line)
        if key not in (*GLOBAL_LIST_KEYS, *GLOBAL_SCALAR_KEYS):
            raise yaml_error(key_line.number, f"global に許さないキーです: {key}")
        if key in values:
            raise yaml_error(key_line.number, f"global のキーが重複しています: {key}")
        value, position = read_value(lines, key_line, position + 1, key, key_rest, map_indent)
        _check_value_type(key, value, key_line, GLOBAL_LIST_KEYS, "global ")
        values[key] = value
    return values, position


def _read_project(lines: list[Line], position: int) -> tuple[Table, int]:
    """`projects` の `- ` で始まる要素 1 つ（`match` と `indexes`）を読み、次に読む行の位置を返す。"""
    first = lines[position]
    after_mark = first.text[len(LIST_ITEM_MARK) :]
    content = after_mark.lstrip(" ")
    # `- ` の後ろのキーの桁に、続くキーが揃う
    key_indent = first.indent + len(LIST_ITEM_MARK) + len(after_mark) - len(content)
    current = Line(number=first.number, indent=key_indent, text=content)
    project: Table = {}
    while True:
        key, rest = split_key(current)
        if key not in (*PROJECT_SCALAR_KEYS, *PROJECT_LIST_KEYS):
            raise yaml_error(current.number, f"projects の要素に許さないキーです: {key}")
        if key in project:
            raise yaml_error(current.number, f"projects の要素のキーが重複しています: {key}")
        value, position = read_value(lines, current, position + 1, key, rest, key_indent)
        _check_value_type(key, value, current, PROJECT_LIST_KEYS, "projects の要素")
        project[key] = value
        # 次の行が同じ桁のキーなら、同じ要素の続き
        if position >= len(lines) or lines[position].indent != key_indent:
            return project, position
        current = lines[position]


def _read_projects(
    lines: list[Line], line: Line, next_position: int, rest: str
) -> tuple[list[Table], int]:
    """`projects` の空のリストか、続く行に並ぶ `- ` で始まる要素のブロックのリストを読む。"""
    if rest.strip() == EMPTY_LIST:
        return [], next_position
    # 同じ行に値がある（フローのリストなど）形式は読まない
    if rest.strip():
        raise yaml_error(line.number, "projects は続く行に `- ` で始まる要素を並べてください")
    projects: list[Table] = []
    position = next_position
    while (
        position < len(lines)
        and lines[position].indent >= line.indent
        and lines[position].text.startswith(LIST_ITEM_MARK)
    ):
        project, position = _read_project(lines, position)
        projects.append(project)
    if not projects:
        raise yaml_error(line.number, "projects の値がありません")
    return projects, position


def parse_settings(text: str) -> Settings:
    """設定ファイルの YAML から `global`（キー → 文字列か文字列のリスト）と `projects`（そのマップのリスト）を返す。"""
    lines = tokenize(text)
    settings: Settings = {}
    position = 0
    while position < len(lines):
        line = lines[position]
        if line.indent != 0:
            raise yaml_error(line.number, "最上位のキーはインデントなしで書いてください")
        key, rest = split_key(line)
        if key not in TOP_KEYS:
            raise yaml_error(line.number, f"許さないキーです: {key}")
        if key in settings:
            raise yaml_error(line.number, f"キーが重複しています: {key}")
        # global はブロックのマップ、projects は要素のリスト
        if key == GLOBAL_KEY:
            settings[key], position = _read_global(lines, line, position + 1, rest)
        else:
            settings[key], position = _read_projects(lines, line, position + 1, rest)
    return settings
