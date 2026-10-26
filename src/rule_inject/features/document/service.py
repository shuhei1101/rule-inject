"""MCP のツールの結果から、文書の場所と範囲を取り出す。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from rule_inject.features.document.types import ResultDocument

# `<document>` の開きタグ（属性の部分を取る）か閉じタグ
TAG_PATTERN = re.compile(r"<document\b([^>]*)>|</document>")
# 開きタグの属性の名前と、二重引用符で囲んだ値
ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)="([^"]*)"')


def _documents_in_text(text: str) -> list[ResultDocument]:
    """文字列から、`path` と `scope` を両方持つ閉じた `<document>` を見つけた順に返す（入れ子の内側は数えない）。"""
    # 開きタグを積み、閉じタグで直近の開きタグと組にする（開始位置・終了位置・属性の部分）
    opened: list[re.Match[str]] = []
    pairs: list[tuple[int, int, str]] = []
    for tag in TAG_PATTERN.finditer(text):
        if tag.group(0).startswith("</"):
            # 組む開きタグが無い閉じタグは読み飛ばす
            if opened:
                opening = opened.pop()
                pairs.append((opening.start(), tag.end(), opening.group(1)))
        else:
            opened.append(tag)
    found: list[ResultDocument] = []
    outer_end = 0
    # 開きタグの順に並べ、前の組の内側に入るもの（入れ子の内側）を除く
    for open_start, close_end, attribute_text in sorted(pairs):
        if open_start < outer_end:
            continue
        outer_end = close_end
        attributes = dict(ATTRIBUTE_PATTERN.findall(attribute_text))
        # path と scope が両方そろったものだけを文書にする
        if "path" in attributes and "scope" in attributes:
            found.append(ResultDocument(path=attributes["path"], scope=attributes["scope"]))
    return found


def _collect(value: Any, found: list[ResultDocument]) -> None:
    """値を深さ優先でたどり、見つけた文書を found へ足す。"""
    if isinstance(value, Mapping):
        # 文字列の path と scope を両方持つオブジェクトは文書にし、続けて全ての値をたどる
        path = value.get("path")
        scope = value.get("scope")
        if isinstance(path, str) and isinstance(scope, str):
            found.append(ResultDocument(path=path, scope=scope))
        for child in value.values():
            _collect(child, found)
    elif isinstance(value, list | tuple):
        for child in value:
            _collect(child, found)
    elif isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            # JSON として読めない文字列は、テキストとして探す
            found.extend(_documents_in_text(value))
            return
        # オブジェクトか配列になれば中をたどり、それ以外の値はテキストとして探す
        if isinstance(parsed, dict | list):
            _collect(parsed, found)
        else:
            found.extend(_documents_in_text(value))


def extract_documents(response: object) -> tuple[ResultDocument, ...]:
    """MCP のツールの結果から、書式に従う文書を見つけた順に返す。"""
    found: list[ResultDocument] = []
    _collect(response, found)
    return tuple(found)
