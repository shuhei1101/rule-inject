"""単一ユースケース「索引をチェックする」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


def test_normal_when_no_violation(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    server_config_path: Path,
    serve: Callable[..., Any],
) -> None:
    """違反の無い索引で、違反とファイルが無いエントリが載らない（正常シナリオ）。"""
    # 準備
    first = make_rule("a.md", "# a\n")
    second = make_rule("b.md", "# b\n")
    index = make_text_file(
        "rules.yaml",
        f'rules:\n  - rule: {first}\n    paths: ["**/*.py"]\n  - rule: {second}\n    on: [write]\n',
    )
    server = serve(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    report = content["indexes"][0]
    assert content["config_path"] == str(server_config_path)
    assert report["index"] == str(index)
    assert report["hook_error"] is None
    assert report["violations"] == []
    assert report["missing_rules"] == []
    assert content["problem_count"] == 0


def test_normal_when_schema_violated(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """Schema に違反するエントリの索引の場所・中の場所・理由を受け取る（正常シナリオ）。"""
    # 準備
    rule = make_rule("a.md", "# a\n")
    index = make_text_file("rules.yaml", f"rules:\n  - rule: {rule}\n    paths: []\n")
    server = serve(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert report["index"] == str(index)
    assert report["violations"][0]["location"] == "rules[0].paths"
    assert report["violations"][0]["reason"]


def test_normal_when_unreadable_by_hook(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """フックが読めない索引は、行の番号を含む理由だけを受け取る（正常シナリオ）。"""
    # 準備
    index = make_text_file("rules.yaml", "rules:\n  - rule: /r/a.md\n    paths: [a,\n      b]\n")
    server = serve(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert "行目" in report["hook_error"]
    assert report["violations"] == []


def test_normal_when_rule_file_missing(
    tmp_path: Path,
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """ルールの場所にファイルが無いエントリの位置と解決した場所を受け取る（正常シナリオ）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    index = make_text_file("rules.yaml", f"rules:\n  - rule: {missing}\n")
    server = serve(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert report["index"] == str(index)
    assert report["missing_rules"] == [{"position": 0, "rule": str(missing)}]
