"""hooks/search_guide.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.guidance.service import SEARCH_HEADER
from rule_inject.hooks.search_guide import search_guide

RULE = "/r/python.md"
OTHER_RULE = "/r/other.md"


@pytest.fixture
def guide_env(
    hook_env: dict[str, str],
    make_index: Callable[..., Path],
) -> Callable[[str], dict[str, str]]:
    """索引の文字列を書き、プロジェクトの索引として指す環境変数を返す factory。"""

    def _env(text: str) -> dict[str, str]:
        """text を索引として置き、hook_env に索引の環境変数を足す。"""
        return {**hook_env, "RULE_INJECT_INDEXES_PROJECT": str(make_index(text))}

    return _env


@pytest.fixture
def python_file(tmp_path: Path) -> Path:
    """検索の結果に出る実在する Python のファイル。"""
    path = tmp_path / "app.py"
    path.write_text("print()\n", encoding="utf-8")
    return path


def test_search_guide(
    state_dir: Path,
    session_id: str,
    python_file: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """Grep の結果に当たるルールを案内する（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"]))
    payload = hook_payload(
        "PostToolUse",
        tool_name="Grep",
        tool_input={"pattern": "print", "path": str(python_file.parent)},
        tool_response={"mode": "files_with_matches", "filenames": [python_file.name]},
    )
    # 実行
    result = search_guide(payload, env)
    # 検証
    output = result["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    assert output["additionalContext"].startswith(SEARCH_HEADER)
    assert RULE in output["additionalContext"]
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [RULE]


def test_search_guide_when_not_search(
    python_file: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """検索でない Bash は見ない（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"]))
    payload = hook_payload(
        "PostToolUse",
        tool_name="Bash",
        tool_input={"command": "git merge main"},
        tool_response={"stdout": f"{python_file}\n", "stderr": ""},
    )
    # 実行
    result = search_guide(payload, env)
    # 検証
    assert result is None


def test_search_guide_when_read_or_guided(
    python_file: Path,
    guide_env: Callable[[str], dict[str, str]],
    hook_payload: Callable[..., dict[str, Any]],
    write_record: Callable[[Sequence[str]], Path],
    write_guided: Callable[[Sequence[str]], Path],
) -> None:
    """既読と案内済みを除く（正常系）。"""
    # 準備
    env = guide_env(
        "rules:\n"
        f"  - rule: {RULE}\n"
        '    paths:\n      - "**/*.py"\n'
        f"  - rule: {OTHER_RULE}\n"
        '    paths:\n      - "**/*.py"\n'
    )
    write_record([RULE])
    write_guided([OTHER_RULE])
    payload = hook_payload(
        "PostToolUse",
        tool_name="Grep",
        tool_input={"pattern": "print", "path": str(python_file.parent)},
        tool_response={"mode": "files_with_matches", "filenames": [python_file.name]},
    )
    # 実行
    result = search_guide(payload, env)
    # 検証
    assert result is None


def test_search_guide_when_invalid_session_id(
    python_file: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """session_id の形が外れていれば案内しない（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"]))
    payload = hook_payload(
        "PostToolUse",
        tool_name="Grep",
        tool_input={"pattern": "print", "path": str(python_file.parent)},
        tool_response={"mode": "files_with_matches", "filenames": [python_file.name]},
        session_id="../x",
    )
    # 実行
    result = search_guide(payload, env)
    # 検証
    assert result is None


def test_search_guide_when_guided_unwritable(
    state_dir: Path,
    session_id: str,
    python_file: Path,
    guide_env: Callable[[str], dict[str, str]],
    index_text: Callable[..., str],
    hook_payload: Callable[..., dict[str, Any]],
    unwritable: Callable[[Path, int], Path],
    read_daily_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """案内済みに書けなくても案内を出す（正常系）。"""
    # 準備
    env = guide_env(index_text(RULE, paths=["**/*.py"]))
    state_dir.mkdir()
    unwritable(state_dir, 0o555)
    payload = hook_payload(
        "PostToolUse",
        tool_name="Grep",
        tool_input={"pattern": "print", "path": str(python_file.parent)},
        tool_response={"mode": "files_with_matches", "filenames": [python_file.name]},
    )
    # 実行
    result = search_guide(payload, env)
    # 検証
    context = result["hookSpecificOutput"]["additionalContext"]
    assert RULE in context
    assert str(state_dir / f"{session_id}.guided.txt") in context
    log_entry = read_daily_log()[0]
    assert log_entry["component"] == "search_guide"
    assert log_entry["operation"] == "write_record"
