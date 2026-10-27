"""shared/_settings_yaml.py の単体テスト。"""

from __future__ import annotations

import re

import pytest

from rule_inject.shared._settings_yaml import parse_settings


def test_parse_settings() -> None:
    """`global` と `projects` を読む（正常系）。"""
    # 準備
    text = (
        "# 設定ファイル\n"
        "global:\n"
        "  indexes:\n"
        "    - ~/rules/a.yaml  # 行末のコメント\n"
        '  state_dir: "/s/state"\n'
        "  log_retention_days: 5\n"
        "projects:\n"
        "  - match: repo\n"
        "    indexes: [rules/b.yaml, rules/c.yaml]\n"
        "  - match: other\n"
    )
    # 実行
    result = parse_settings(text)
    # 検証
    assert result == {
        "global": {
            "indexes": ["~/rules/a.yaml"],
            "state_dir": "/s/state",
            "log_retention_days": "5",
        },
        "projects": [
            {"match": "repo", "indexes": ["rules/b.yaml", "rules/c.yaml"]},
            {"match": "other"},
        ],
    }


def test_parse_settings_when_empty() -> None:
    """コメントだけの設定ファイルは空の dict にする（正常系）。"""
    # 実行
    result = parse_settings("# コメントだけ\n\n")
    # 検証
    assert result == {}


def test_parse_settings_when_empty_lists() -> None:
    """空のリストを読む（正常系）。"""
    # 実行
    result = parse_settings("global:\n  indexes: []\nprojects: []\n")
    # 検証
    assert result == {"global": {"indexes": []}, "projects": []}


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("foo: 1\n", id="top_level"),
        pytest.param("global:\n  index:\n    - /a.yaml\n", id="global"),
        pytest.param("projects:\n  - match: repo\n    state_dir: /s\n", id="projects"),
    ],
)
def test_parse_settings_when_unknown_key(text: str) -> None:
    """許さないキーを拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=re.compile(r"\d+行目")):
        parse_settings(text)


def test_parse_settings_when_flow_map() -> None:
    """フローのマップを拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=re.compile(r"\d+行目")):
        parse_settings("global: {state_dir: /s}\n")


def test_parse_settings_when_duplicate_key() -> None:
    """キーの重複を拒む（異常系）。"""
    # 実行・検証
    with pytest.raises(ValueError, match=re.compile(r"\d+行目")):
        parse_settings("global:\n  log_dir: /a\n  log_dir: /b\n")
