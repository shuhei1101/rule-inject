"""features/index/edit/_yaml.py の単体テスト。"""

from __future__ import annotations

import io

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from rule_inject.features.index._yaml import parse_index

LONG_GLOB = "**/some/very/long/folder/name/that/goes/on/and/on/and/on/until/it/passes/eighty/*.py"


def test_round_trip_yaml() -> None:
    """書き換えない索引は 1 バイトも変わらずに書き戻る（正常系）。"""
    from rule_inject.features.index.edit._yaml import round_trip_yaml

    # 準備
    text = (
        "# ルールの索引\n"
        "default_on: [write]  # 既定\n"
        "rules:\n"
        "  # python のルール\n"
        "  - rule: 'python.md'\n"
        f'    paths: ["{LONG_GLOB}", "**/*.pyi"]\n'
        '  - rule: "ts.md"\n'
        "    on: [read]\n"
    )
    yaml = round_trip_yaml()
    buffer = io.StringIO()
    # 実行
    yaml.dump(yaml.load(text), buffer)
    # 検証
    assert buffer.getvalue() == text


def test_to_yaml_value() -> None:
    """キーごとの書式で書き出す（正常系）。"""
    from rule_inject.features.index.edit._yaml import round_trip_yaml, to_yaml_value

    # 準備
    values = {
        "rule": "a.md",
        "paths": ["**/*.py"],
        "args": {"doc_path": ["dev/**"]},
        "read_by": [{"tools": ["mcp__a"], "args": {"path": ["x"]}}],
    }
    entry = CommentedMap()
    for key, value in values.items():
        entry[key] = to_yaml_value(key, value)
    document = CommentedMap()
    document["rules"] = CommentedSeq([entry])
    buffer = io.StringIO()
    # 実行
    round_trip_yaml().dump(document, buffer)
    # 検証
    text = buffer.getvalue()
    lines = text.splitlines()
    assert "    args:" in lines
    assert "    read_by:" in lines
    assert any(line.startswith("    paths: [") and line.endswith("]") for line in lines)
    assert parse_index(text)[1] == [values]
