"""MCP のツールの結果から、文書の場所と範囲を取り出す。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from rule_inject.features.document.types import ResultDocument

# 閉じタグまでそろった `<document>`（本文の途中に別の `<document` の開きタグを含むものは、閉じていないものとして数えない）
DOCUMENT_PATTERN = re.compile(
    r"<document\b([^>]*)>(?:(?!<document\b).)*?</document>",
    re.DOTALL,
)
# 開きタグの属性の名前と、二重引用符で囲んだ値
ATTRIBUTE_PATTERN = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)="([^"]*)"')


def _documents_in_text(text: str) -> list[ResultDocument]:
    """文字列から、`path` と `scope` を両方持つ閉じた `<document>` を見つけた順に返す。"""
    found: list[ResultDocument] = []
    for match in DOCUMENT_PATTERN.finditer(text):
        attributes = dict(ATTRIBUTE_PATTERN.findall(match.group(1)))
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
