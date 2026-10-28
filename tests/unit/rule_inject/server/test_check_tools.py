"""server/check_tools.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

# 辿る時間の上限（秒）。辿り終えられる値
SCAN_TIME_LIMIT = 30


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """ツールに渡すプロジェクトの直下。"""
    path = tmp_path / "project"
    path.mkdir()
    return path


@pytest.fixture
def unmatched_env(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    server_env: Callable[..., dict[str, str]],
) -> dict[str, str]:
    """`global.indexes` とプロジェクトの索引の両方に、どのファイルにも当たらないエントリを 1 つずつ置いた設定ファイルを指す環境変数。"""
    app = project_dir / "src" / "app.py"
    app.parent.mkdir()
    app.write_text("", encoding="utf-8")
    global_index = make_index(
        f'rules:\n  - rule: {rule_file("global.md")}\n    paths: ["**/*.java"]\n', "global.yaml"
    )
    project_index = make_index(
        f'rules:\n  - rule: {rule_file("project.md")}\n    paths: ["**/*.rs"]\n', "project.yaml"
    )
    return server_env(
        "global:\n"
        "  indexes:\n"
        f"    - {global_index}\n"
        "projects:\n"
        f"  - match: {project_dir}\n"
        "    indexes:\n"
        f"      - {project_index}\n"
    )


def test_check_indexes(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    indexes_env: Callable[..., dict[str, str]],
) -> None:
    """問題を種類ごとに分け、件数を合計する（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 準備
    rule = rule_file()
    index = make_index(f"rules:\n  - rule: {rule}\n    paths: []\n  - rule: /nonexistent/x.md\n")
    missing = tmp_path / "missing.yaml"
    env = indexes_env(index, missing)
    # 実行
    result = check_indexes(
        project_dir=str(project_dir),
        format="json",
        env=env,
        validator=load_validator(),
        scan_time_limit=SCAN_TIME_LIMIT,
    )
    # 検証
    content = result.structured_content
    assert content["problem_count"] == 3
    assert content["indexes"][0]["origin"] == "global"
    assert content["indexes"][1]["hook_error"] is not None
    assert content["indexes"][1]["violations"] == []
    assert content["indexes"][1]["missing_rules"] == []


def test_check_indexes_when_unmatched(
    tmp_path: Path,
    project_dir: Path,
    unmatched_env: dict[str, str],
) -> None:
    """プロジェクトの索引の `paths` の当たらないエントリだけを載せて数える（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 実行
    result = check_indexes(
        project_dir=str(project_dir),
        format="json",
        env=unmatched_env,
        validator=load_validator(),
        scan_time_limit=SCAN_TIME_LIMIT,
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert [
        (entry["position"], entry["rule"]) for entry in reports["project"]["unmatched_paths"]
    ] == [(0, str(tmp_path / "rules" / "project.md"))]
    assert reports["global"]["unmatched_paths"] == []
    assert content["problem_count"] == 1


def test_check_indexes_when_include_global(
    tmp_path: Path,
    project_dir: Path,
    unmatched_env: dict[str, str],
) -> None:
    """`include_global` でユーザー全体の索引も載せ、数えない（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 実行
    result = check_indexes(
        project_dir=str(project_dir),
        format="json",
        include_global=True,
        env=unmatched_env,
        validator=load_validator(),
        scan_time_limit=SCAN_TIME_LIMIT,
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert [
        (entry["position"], entry["rule"]) for entry in reports["global"]["unmatched_paths"]
    ] == [(0, str(tmp_path / "rules" / "global.md"))]
    assert [
        (entry["position"], entry["rule"]) for entry in reports["project"]["unmatched_paths"]
    ] == [(0, str(tmp_path / "rules" / "project.md"))]
    assert content["problem_count"] == 1


def test_check_indexes_when_time_limit(
    project_dir: Path,
    unmatched_env: dict[str, str],
) -> None:
    """辿る時間の上限で止まると続きの位置を返し、渡すと続きから辿る（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 準備
    readme = project_dir / "docs" / "readme.md"
    readme.parent.mkdir()
    readme.write_text("", encoding="utf-8")
    validator = load_validator()
    # 実行
    first = check_indexes(
        project_dir=str(project_dir),
        format="json",
        env=unmatched_env,
        validator=validator,
        scan_time_limit=0,
    )
    second = check_indexes(
        project_dir=str(project_dir),
        format="json",
        cursor=first.structured_content["unmatched_scan"]["next_cursor"],
        env=unmatched_env,
        validator=validator,
        scan_time_limit=0,
    )
    # 検証
    first_scan = first.structured_content["unmatched_scan"]
    second_scan = second.structured_content["unmatched_scan"]
    assert first_scan["completed"] is False
    assert "cursor" in first_scan["reason"]
    assert "秒" in first_scan["reason"]
    assert first_scan["next_cursor"] is not None
    assert second_scan["completed"] is True
    assert second_scan["scanned_files"] == 2


def test_check_indexes_when_cursor_invalid(
    project_dir: Path,
    unmatched_env: dict[str, str],
) -> None:
    """使えない `cursor` を断る（異常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 実行・検証
    with pytest.raises(ToolError, match="cursor"):
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            cursor="broken",
            env=unmatched_env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
        )


def test_decode_scan_cursor() -> None:
    """文字列にした続きの位置を戻す（正常系）。"""
    from rule_inject.features.index.check.types import ScanCursor
    from rule_inject.server.check_tools import _decode_scan_cursor, _encode_scan_cursor

    # 準備
    cursor = ScanCursor(
        last_file="docs/readme.md",
        scanned_files=1,
        unmatched=(("/i/rules.yaml", 1, "3f9a1c0b2d4e"),),
        fingerprint="abc123",
    )
    encoded = _encode_scan_cursor(cursor, "/p", False)
    # 実行
    result = _decode_scan_cursor(encoded, "/p", False)
    # 検証
    assert result == cursor


def test_decode_scan_cursor_when_mismatched() -> None:
    """呼び出しの引数が違えば断る（異常系）。"""
    from rule_inject.features.index.check.types import ScanCursor
    from rule_inject.server.check_tools import _decode_scan_cursor, _encode_scan_cursor

    # 準備
    cursor = ScanCursor(
        last_file="docs/readme.md",
        scanned_files=1,
        unmatched=(("/i/rules.yaml", 1, "3f9a1c0b2d4e"),),
        fingerprint="abc123",
    )
    encoded = _encode_scan_cursor(cursor, "/p", False)
    # 実行・検証
    with pytest.raises(ToolError, match="cursor"):
        _decode_scan_cursor(encoded, "/p", True)
