"""round-trip の設定と、書き込む値の書式。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import SingleQuotedScalarString

# 1 行のフロー形式のリストを折り返さない行の長さ
YAML_WIDTH = 4096
MAPPING_INDENT = 2
SEQUENCE_INDENT = 4
# `  - rule:` の字下げ
SEQUENCE_OFFSET = 2
# 値が文字列のリストで、1 行のフロー形式で書くキー
FLOW_LIST_KEYS = ("paths", "exclude", "tools", "on")
ARGS_KEY = "args"
READ_BY_KEY = "read_by"
READ_BY_TOOLS_KEY = "tools"
READ_TOOL_KEY = "read_tool"
# `read_tool` のマップのキーの並び（`args`・`optional_args` は JSON の文字列）
READ_TOOL_KEY_ORDER = ("tool", "args", "optional_args")
READ_TOOL_JSON_KEYS = ("args", "optional_args")


def round_trip_yaml(
    *,
    mapping: int = MAPPING_INDENT,
    sequence: int = SEQUENCE_INDENT,
    offset: int = SEQUENCE_OFFSET,
) -> YAML:
    """フックの読み取りが受け付ける書式で書き戻す `YAML` を作る（スレッドをまたいで共有しないため、呼ぶたびに作る）。"""
    yaml = YAML()
    yaml.width = YAML_WIDTH
    yaml.indent(mapping=mapping, sequence=sequence, offset=offset)
    yaml.preserve_quotes = True
    return yaml


def _flow_list(values: Sequence[Any]) -> CommentedSeq:
    """1 行のフロー形式のリストにする。"""
    seq = CommentedSeq(values)
    seq.fa.set_flow_style()
    return seq


def _arguments(value: Mapping[str, Any]) -> CommentedMap:
    """引数の条件を、キーごとのリストを 1 行のフロー形式にしたブロックのマップにする。"""
    mapping = CommentedMap()
    for key, patterns in value.items():
        mapping[key] = _flow_list(patterns) if isinstance(patterns, list) else patterns
    return mapping


def _read_by_item(value: Any) -> Any:
    """`read_by` の要素のマップに、`tools` と `args` の書式を当てる。"""
    if not isinstance(value, Mapping):
        return value
    item = CommentedMap()
    for key, inner in value.items():
        if key == READ_BY_TOOLS_KEY and isinstance(inner, list):
            item[key] = _flow_list(inner)
        elif key == ARGS_KEY and isinstance(inner, Mapping):
            item[key] = _arguments(inner)
        else:
            item[key] = inner
    return item


def _read_tool(value: Mapping[str, Any]) -> CommentedMap:
    """`read_tool` のマップを `tool`・`args`・`optional_args` の順にし、JSON の文字列を単一引用符で書く。"""
    mapping = CommentedMap()
    ordered = [key for key in READ_TOOL_KEY_ORDER if key in value]
    ordered.extend(key for key in value if key not in READ_TOOL_KEY_ORDER)
    for key in ordered:
        inner = value[key]
        # JSON は二重引用符を含むため、単一引用符で囲んだ 1 行の文字列にする
        is_json_text = key in READ_TOOL_JSON_KEYS and isinstance(inner, str)
        mapping[key] = SingleQuotedScalarString(inner) if is_json_text else inner
    return mapping


def to_yaml_value(key: str, value: Any) -> Any:
    """ツールの引数の `entry` の値を、キーごとの書式を指定した round-trip の値にする。型の合わない値はそのまま返す。"""
    # 文字列のリストは 1 行のフロー形式、`args` はブロックのマップ、`read_by` はブロックのリスト、`read_tool` はブロックのマップ
    if key in FLOW_LIST_KEYS and isinstance(value, list):
        return _flow_list(value)
    if key == ARGS_KEY and isinstance(value, Mapping):
        return _arguments(value)
    if key == READ_BY_KEY and isinstance(value, list):
        return CommentedSeq(_read_by_item(item) for item in value)
    if key == READ_TOOL_KEY and isinstance(value, Mapping):
        return _read_tool(value)
    return value
