"""shared/yaml_lines.py の単体テスト。"""

from __future__ import annotations

import pytest

from rule_inject.shared.yaml_lines import (
    Line,
    parse_flow_list,
    parse_scalar,
    read_block_list,
    read_value,
    split_key,
    tokenize,
    yaml_error,
)


def test_yaml_error() -> None:
    """行番号つきのメッセージ（正常系）。"""
    # 実行
    result = yaml_error(3, "値が空です")
    # 検証
    assert isinstance(result, ValueError)
    assert str(result) == "3行目: 値が空です"


def test_tokenize() -> None:
    """コメントと空行を落として行番号とインデントを持たせる（正常系）。"""
    # 準備
    text = 'a: 1  # c\n\n  - "#x"\n'
    # 実行
    result = tokenize(text)
    # 検証
    assert result == [
        Line(number=1, indent=0, text="a: 1"),
        Line(number=3, indent=2, text='- "#x"'),
    ]


def test_tokenize_when_hash_in_word() -> None:
    """語の途中の `#` はコメントにしない（正常系）。"""
    # 実行
    result = tokenize("a: b#c\n")
    # 検証
    assert result == [Line(number=1, indent=0, text="a: b#c")]


def test_tokenize_when_tab_indent() -> None:
    """タブのインデントを拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^2行目: インデントにタブは使えません$"):
        tokenize("a:\n\t- x\n")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param(" abc ", "abc", id="plain"),
        pytest.param('"a\\"b"', 'a"b', id="double_quote"),
        pytest.param("'it''s'", "it's", id="single_quote"),
    ],
)
def test_parse_scalar(text: str, expected: str) -> None:
    """引用符あり・なしを読む（正常系）。"""
    # 実行
    result = parse_scalar(text, 1)
    # 検証
    assert result == expected


def test_parse_scalar_when_empty() -> None:
    """空の値を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: 値が空です$"):
        parse_scalar("  ", 1)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('"abc', id="no_closing"),
        pytest.param('"', id="quote_only"),
    ],
)
def test_parse_scalar_when_unclosed_quote(text: str) -> None:
    """閉じていない引用符を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: 引用符が閉じていません$"):
        parse_scalar(text, 1)


def test_parse_scalar_when_reserved_head() -> None:
    """別の意味になる先頭の文字を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: 先頭が \* の値は引用符で囲んでください$"):
        parse_scalar("*abc", 1)


def test_parse_flow_list() -> None:
    """要素を読む（正常系）。"""
    # 実行
    result = parse_flow_list("[a, \"b, c\", 'd']", 1)
    # 検証
    assert result == ["a", "b, c", "d"]


def test_parse_flow_list_when_empty() -> None:
    """空のリスト（正常系）。"""
    # 実行
    result = parse_flow_list("[ ]", 1)
    # 検証
    assert result == []


def test_parse_flow_list_when_unclosed_bracket() -> None:
    """閉じていないリストを拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: リストが `\]` で閉じていません$"):
        parse_flow_list("[a, b", 1)


def test_parse_flow_list_when_unclosed_quote() -> None:
    """要素の閉じていない引用符を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: 引用符が閉じていません$"):
        parse_flow_list('["a, b]', 1)


def test_parse_flow_list_when_empty_item() -> None:
    """空の要素を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: 値が空です$"):
        parse_flow_list("[a, , b]", 1)


def test_read_block_list() -> None:
    """続く要素の行を読み、次の位置を返す（正常系）。"""
    # 準備
    lines = tokenize('a:\n  - x\n  - "y"\nb: 1\n')
    # 実行
    result = read_block_list(lines, 1, 1)
    # 検証
    assert result == (["x", "y"], 3)


def test_read_block_list_when_shallow() -> None:
    """浅いインデントの行で止める（正常系）。"""
    # 準備
    lines = tokenize("- x\n")
    # 実行
    result = read_block_list(lines, 0, 1)
    # 検証
    assert result == ([], 0)


def test_split_key() -> None:
    """キーと残りに分ける（正常系）。"""
    # 準備
    line = Line(number=1, indent=0, text="state_dir: ~/a:b")
    # 実行
    result = split_key(line)
    # 検証
    assert result == ("state_dir", " ~/a:b")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("abc", id="no_colon"),
        pytest.param(": x", id="empty_key"),
        pytest.param("a b: x", id="space_in_key"),
    ],
)
def test_split_key_when_invalid(text: str) -> None:
    """キーの形式でない行を拒む（異常系）。"""
    # 準備
    line = Line(number=1, indent=0, text=text)
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: `キー: 値` の形式で書いてください$"):
        split_key(line)


@pytest.mark.parametrize(
    ("rest", "expected"),
    [
        pytest.param(" abc", ("abc", 1), id="scalar"),
        pytest.param(" [a, b]", (["a", "b"], 1), id="flow_list"),
    ],
)
def test_read_value(rest: str, expected: tuple[str | list[str], int]) -> None:
    """同じ行の文字列とフローのリストを読む（正常系）。"""
    # 準備
    line = Line(number=1, indent=0, text=f"key:{rest}")
    # 実行
    result = read_value([line], line, 1, "key", rest, 1)
    # 検証
    assert result == expected


def test_read_value_when_block_list() -> None:
    """続く行のブロックのリストを読む（正常系）。"""
    # 準備
    lines = tokenize("key:\n  - x\n  - y\nother: 1\n")
    # 実行
    result = read_value(lines, lines[0], 1, "key", "", 1)
    # 検証
    assert result == (["x", "y"], 3)


def test_read_value_when_missing() -> None:
    """値が無いキーを拒む（異常系）。"""
    # 準備
    lines = tokenize("key:\nother: 1\n")
    # 実行・検証
    with pytest.raises(ValueError, match=r"^1行目: key の値がありません$"):
        read_value(lines, lines[0], 1, "key", "", 1)
