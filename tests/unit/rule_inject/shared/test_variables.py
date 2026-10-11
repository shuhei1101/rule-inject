"""shared/variables.py の単体テスト。"""

from __future__ import annotations

from rule_inject.shared.variables import expand_variables


def test_expand_variables() -> None:
    """設定された名前を展開する（正常系）。"""
    # 実行
    result = expand_variables("a !{X} b !{X}", {"X": "1"})
    # 検証
    assert result.text == "a 1 b 1"
    assert result.unresolved == ()


def test_expand_variables_when_empty_value() -> None:
    """空の値は空文字にする（正常系）。"""
    # 実行
    result = expand_variables("[!{E}]", {"E": ""})
    # 検証
    assert result.text == "[]"
    assert result.unresolved == ()


def test_expand_variables_when_unset() -> None:
    """未設定の名前を残して並べる（正常系）。"""
    # 実行
    result = expand_variables("!{B} !{A} !{B}", {})
    # 検証
    assert result.text == "!{B} !{A} !{B}"
    assert result.unresolved == ("B", "A")


def test_expand_variables_when_not_name() -> None:
    """名前の形に合わないものは置き換えない（正常系）。"""
    # 実行
    result = expand_variables("!{ X } !{1X} {X} $X", {"X": "1"})
    # 検証
    assert result.text == "!{ X } !{1X} {X} $X"
    assert result.unresolved == ()


def test_expand_variables_when_value_has_reference() -> None:
    """値の中の変数参照は展開し直さない（正常系）。"""
    # 実行
    result = expand_variables("!{X}", {"X": "!{Y}", "Y": "2"})
    # 検証
    assert result.text == "!{Y}"
