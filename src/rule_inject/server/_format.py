"""応答の形式（JSON / Markdown）と長さの切り詰め。"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from mcp.types import CallToolResult, TextContent
from pydantic import BaseModel

from rule_inject.server.types import ResponseFormat

# 応答の text の字数の上限
MAX_RESPONSE_CHARS = 40_000
OUTPUT_KEY = "output"
DIFF_KEY = "diff"
EMPTY_LIST_TEXT = "なし"
# 入れ子の表にする、行の中のリストのキー
NESTED_TABLE_KEYS = ("violations", "missing_rules", "skipped_entries")


def _cell(value: Any) -> str:
    """表のセルの文字列にする。リスト・マップは JSON の 1 行にし、表を崩す文字は置き換える。"""
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text.replace("|", "\\|").replace("\n", "<br>")


def _table(rows: Sequence[Mapping[str, Any]], skip: Sequence[str] = ()) -> list[str]:
    """マップのリストを、キーを列にした Markdown の表の行にする。"""
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns and key not in skip:
                columns.append(key)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(row.get(key)) for key in columns) + " |" for row in rows)
    return lines


def _is_row_list(value: Any) -> bool:
    """マップのリスト（表にする値）か。"""
    return (
        isinstance(value, list) and bool(value) and all(isinstance(item, Mapping) for item in value)
    )


def _list_section(name: str, items: list[Any]) -> list[str]:
    """リストの項目を、見出しと表（文字列のリストは箇条書き、空のリストは「なし」）にする。"""
    lines = ["", f"## {name}", ""]
    if not items:
        return [*lines, EMPTY_LIST_TEXT]
    if not _is_row_list(items):
        return [*lines, *(f"- {_cell(item)}" for item in items)]
    # 行の中のマップのリストは、親の行ごとに別の表にする
    nested = [key for key in NESTED_TABLE_KEYS if any(key in item for item in items)]
    lines.extend(_table(items, skip=nested))
    for number, item in enumerate(items):
        for key in nested:
            if key in item:
                lines.extend(["", f"### {name}[{number}].{key}", ""])
                lines.extend(_table(item[key]) if item[key] else [EMPTY_LIST_TEXT])
    return lines


def render_markdown(result: BaseModel) -> str:
    """応答のモデルの各項目を Markdown にする。"""
    data = result.model_dump(mode="json")
    lines = [str(data[OUTPUT_KEY])]
    sections: list[str] = []
    for key, value in data.items():
        if key == OUTPUT_KEY:
            continue
        if isinstance(value, list):
            sections.extend(_list_section(key, value))
        elif key == DIFF_KEY:
            sections.extend(["", "```diff", str(value).rstrip("\n"), "```"])
        else:
            lines.append(f"- {key}: {_cell(value)}")
    return "\n".join([*lines, *sections]) + "\n"


def respond(result: BaseModel, format: ResponseFormat) -> CallToolResult:
    """応答のモデルを、形式に合わせた `CallToolResult` にする。"""
    # json は structuredContent と text に同じ JSON を入れ、markdown は text だけに入れる
    if format == "json":
        data = result.model_dump(mode="json", exclude_none=False)
        text = json.dumps(data, ensure_ascii=False)
        return CallToolResult(
            content=[TextContent(type="text", text=text)], structured_content=data
        )
    return CallToolResult(content=[TextContent(type="text", text=render_markdown(result))])


def _text_length(result: BaseModel, format: ResponseFormat) -> int:
    """応答の text の字数を返す。"""
    content = respond(result, format).content[0]
    return len(content.text) if isinstance(content, TextContent) else 0


def fit_page(
    build: Callable[[int], BaseModel], count: int, format: ResponseFormat
) -> tuple[BaseModel, int]:
    """応答の text が上限に収まるまで、一覧の末尾から要素を切る。収まる最大の件数の応答と、その件数を返す。"""
    # 件数を二分探索で減らす（0 件でも超えるときは 0 件の応答を返す）
    low, high = 0, count
    while low < high:
        middle = (low + high + 1) // 2
        if _text_length(build(middle), format) <= MAX_RESPONSE_CHARS:
            low = middle
        else:
            high = middle - 1
    return build(low), low
