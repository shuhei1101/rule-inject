"""server/tools.py の単体テスト。"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from rule_inject.shared.settings import load_settings


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """ツールに渡すプロジェクトの直下。"""
    path = tmp_path / "project"
    path.mkdir()
    return path


def test_list_rules_when_paged(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    indexes_env: Callable[..., dict[str, str]],
) -> None:
    """`limit` と `cursor` で続きを返し、理由の一覧は先頭のページだけに載せる（正常系）。"""
    from rule_inject.server.tools import list_rules

    # 準備
    index = make_index(
        "rules:\n"
        "  - rule: /r/a.md\n"
        "  - rule: /r/b.md\n"
        "  - rule: /r/off.md\n"
        "    enabled: false\n"
        "  - rule: /r/c.md\n"
    )
    env = indexes_env(index)
    # 実行
    first = list_rules(project_dir=str(project_dir), limit=2, cursor=None, format="json", env=env)
    second = list_rules(project_dir=str(project_dir), limit=2, cursor="2", format="json", env=env)
    # 検証
    assert len(first.structured_content["entries"]) == 2
    assert first.structured_content["next_cursor"] == "2"
    assert len(first.structured_content["disabled_entries"]) == 1
    assert first.structured_content["total"] == 3
    assert len(second.structured_content["entries"]) == 1
    assert second.structured_content["next_cursor"] is None
    assert second.structured_content["disabled_entries"] == []
    assert second.structured_content["total"] == 3


def test_search_rules_when_same_rule(
    project_dir: Path,
    make_index: Callable[..., Path],
    indexes_env: Callable[..., dict[str, str]],
) -> None:
    """同じルールに当たったエントリを 1 件にまとめ、どれかが止めれば止める（正常系）。"""
    from rule_inject.server.tools import search_rules

    # 準備
    index = make_index(
        "rules:\n"
        "  - rule: /r/python.md\n"
        '    paths: ["**/*.py"]\n'
        "    on: [read]\n"
        "  - rule: /r/python.md\n"
        '    paths: ["**/*.py"]\n'
        "    on: [write]\n"
    )
    env = indexes_env(index)
    # 実行
    result = search_rules(
        project_dir=str(project_dir),
        path="/p/src/a.py",
        operation="write",
        format="json",
        env=env,
    )
    # 検証
    matched = result.structured_content["matched"]
    assert len(matched) == 1
    assert matched[0]["rule"] == "/r/python.md"
    assert matched[0]["blocking"] is True
    assert len(matched[0]["entries"]) == 2


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param(
            {"path": "/p/a.py", "operation": "write", "tool_name": "mcp__a__b"}, id="both"
        ),
        pytest.param({}, id="neither"),
        pytest.param({"path": "/p/a.py"}, id="no_operation"),
        pytest.param({"path": "p/a.py", "operation": "write"}, id="relative_path"),
    ],
)
def test_search_rules_when_invalid_arguments(
    project_dir: Path,
    arguments: dict[str, Any],
) -> None:
    """引数の組み合わせの誤りを拒む（異常系）。"""
    from rule_inject.server.tools import search_rules

    # 実行・検証
    with pytest.raises(ToolError):
        search_rules(project_dir=str(project_dir), format="json", env={}, **arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param({"position": 0}, id="position_without_rev"),
        pytest.param({"remove_keys": ["on"]}, id="remove_keys_without_position"),
        pytest.param(
            {
                "entry": {"rule": "a.md", "on": ["read"]},
                "position": 0,
                "expected_rev": "x",
                "remove_keys": ["on"],
            },
            id="same_key",
        ),
    ],
)
def test_write_index_entry_when_invalid_arguments(
    project_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: dict[str, Any],
) -> None:
    """引数の組み合わせの誤りを拒む（異常系）。"""
    from rule_inject.features.index.edit import IndexLocks
    from rule_inject.server.tools import write_index_entry

    # 準備
    calls: list[tuple[Any, ...]] = []

    def _write_entry(*args: Any, **kwargs: Any) -> None:
        """呼ばれたことを控える（呼ばれてはならない）。"""
        calls.append((args, kwargs))

    monkeypatch.setattr("rule_inject.server.tools.write_entry", _write_entry)
    kwargs: dict[str, Any] = {"entry": {"rule": "a.md"}}
    kwargs.update(arguments)
    # 実行・検証
    with pytest.raises(ToolError):
        write_index_entry(
            project_dir=str(project_dir),
            index=str(project_dir / "rules.yaml"),
            env={},
            locks=IndexLocks(),
            check_change=lambda *args: (),
            **kwargs,
        )
    assert calls == []


def test_project_settings_when_project_matched(
    server_env: Callable[..., dict[str, str]],
) -> None:
    """`project_dir` で `projects[].match` を当てる（正常系）。"""
    from rule_inject.server.tools import _project_settings

    # 準備
    env = server_env("projects:\n  - match: /home/user/project\n    indexes:\n      - rules.yaml\n")
    # 実行
    settings = _project_settings("/home/user/project", env)
    # 検証
    assert settings.indexes[-1] == "/home/user/project/rules.yaml"


def test_project_settings_when_relative() -> None:
    """相対パスを拒む（異常系）。"""
    from rule_inject.server.tools import _project_settings

    # 実行・検証
    with pytest.raises(ToolError):
        _project_settings("project", {})


def test_editable_index_when_symlink(
    tmp_path: Path,
    make_index: Callable[..., Path],
    indexes_env: Callable[..., dict[str, str]],
) -> None:
    """シンボリックリンクを解いて比べる（正常系）。"""
    from rule_inject.server.tools import _editable_index

    # 準備
    index = make_index("rules: []\n")
    link = tmp_path / "link.yaml"
    link.symlink_to(index)
    settings = load_settings(indexes_env(index))
    # 実行
    result = _editable_index(str(link), settings)
    # 検証
    assert result == os.path.realpath(index)


def test_editable_index_when_not_read(
    make_index: Callable[..., Path],
    indexes_env: Callable[..., dict[str, str]],
) -> None:
    """読む索引でないファイルを拒む（異常系）。"""
    from rule_inject.server.tools import _editable_index

    # 準備
    index = make_index("rules: []\n", "index.yaml")
    other = make_index("rules: []\n", "other.yaml")
    settings = load_settings(indexes_env(index))
    # 実行・検証
    with pytest.raises(ToolError) as raised:
        _editable_index(str(other), settings)
    assert str(index) in str(raised.value)
