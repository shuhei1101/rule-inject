"""features/document/service.py の単体テスト。"""

from __future__ import annotations

import pytest

from rule_inject.features.document.service import extract_documents
from rule_inject.features.document.types import ResultDocument


def test_extract_documents_when_markdown() -> None:
    """閉じた `<document>` を順に取り出す（正常系）。"""
    # 準備
    response = (
        '<document path="a.md" scope="full">本文 A</document>\n'
        '<document path="b.md" scope="summary">説明 B</document>'
    )
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (
        ResultDocument(path="a.md", scope="full"),
        ResultDocument(path="b.md", scope="summary"),
    )


def test_extract_documents_when_unclosed() -> None:
    """閉じタグの無い `<document>` は数えない（正常系）。"""
    # 準備
    response = '<document path="a.md" scope="full">閉じていない本文\n<document path="b.md" scope="full">本文 B</document>'
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (ResultDocument(path="b.md", scope="full"),)


def test_extract_documents_when_nested() -> None:
    """本文に入れ子で載った `<document>` は数えず、外側の文書を取り出す（正常系）。"""
    # 準備
    response = (
        '<document path="a.md" scope="full">'
        '例: <document path="b.md" scope="full">本文 B</document>'
        "</document>"
    )
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (ResultDocument(path="a.md", scope="full"),)


def test_extract_documents_when_json_items() -> None:
    """どの深さのオブジェクトの `path`・`scope` も取り出す（正常系）。"""
    # 準備
    response = {
        "items": [{"path": "a.md", "scope": "full", "body": "本文 A"}],
        "meta": {"child": {"path": "b.md", "scope": "section"}},
    }
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (
        ResultDocument(path="a.md", scope="full"),
        ResultDocument(path="b.md", scope="section"),
    )


def test_extract_documents_when_json_string() -> None:
    """文字列に入った JSON もたどる（正常系）。"""
    # 準備
    response = {"result": '{"items": [{"path": "a.md", "scope": "full"}]}'}
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (ResultDocument(path="a.md", scope="full"),)


def test_extract_documents_when_text_in_json() -> None:
    """JSON の値の文字列から `<document>` を取り出す（正常系）。"""
    # 準備
    response = {"result": '<document path="a.md" scope="full">本文 A</document>'}
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (ResultDocument(path="a.md", scope="full"),)


def test_extract_documents_when_not_json() -> None:
    """JSON として読めない文字列はテキストとして探す（正常系）。"""
    # 準備
    response = '{broken <document path="a.md" scope="full">本文 A</document>'
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == (ResultDocument(path="a.md", scope="full"),)


def test_extract_documents_when_attribute_missing() -> None:
    """`path` か `scope` が欠けたものは文書にしない（正常系）。"""
    # 準備
    response = [
        '<document path="a.md">本文 A</document>',
        {"path": "b.md", "scope": 1},
    ]
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == ()


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(None, id="none"),
        pytest.param(1, id="integer"),
    ],
)
def test_extract_documents_when_not_container(response: object) -> None:
    """文字列・オブジェクト・配列でなければ文書は無い（正常系）。"""
    # 実行
    result = extract_documents(response)
    # 検証
    assert result == ()
