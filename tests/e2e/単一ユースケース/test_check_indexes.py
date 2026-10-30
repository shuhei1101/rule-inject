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
    source = e2e_project / "src" / "app.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("", encoding="utf-8")
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
    assert report["unmatched_paths"] == []
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


def _unmatched_environment(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
) -> tuple[Path, Path, Path, Path]:
    """プロジェクトのファイルと、プロジェクトの索引・ユーザー全体の索引を置き、2 つの索引とルールの本文を返す。"""
    project_rule = make_rule("project.md", "# project\n")
    global_rule = make_rule("global.md", "# global\n")
    source = e2e_project / "src" / "app.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("", encoding="utf-8")
    project_index = make_text_file(
        "rules.yaml",
        f'rules:\n  - rule: {project_rule}\n    paths: ["**/*.py"]\n'
        f'  - rule: {project_rule}\n    paths: ["**/*.rs"]\n',
    )
    global_index = make_text_file(
        "user/rules.yaml", f'rules:\n  - rule: {global_rule}\n    paths: ["**/*.go"]\n'
    )
    return project_index, global_index, project_rule, global_rule


def test_normal_when_paths_unmatched(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """プロジェクトの索引の `paths` の当たらないエントリを受け取り、ユーザー全体の索引の分は受け取らない（正常シナリオ）。"""
    # 準備
    project_index, global_index, project_rule, _ = _unmatched_environment(
        e2e_project, make_text_file, make_rule
    )
    before = (project_index.read_text(encoding="utf-8"), global_index.read_text(encoding="utf-8"))
    server = serve(project_index, global_indexes=[global_index])
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    reports = {report["origin"]: report for report in result.structured_content["indexes"]}
    assert reports["project"]["index"] == str(project_index)
    assert [
        (entry["position"], entry["rule"]) for entry in reports["project"]["unmatched_paths"]
    ] == [(1, str(project_rule))]
    assert reports["global"]["unmatched_paths"] == []
    assert (
        project_index.read_text(encoding="utf-8"),
        global_index.read_text(encoding="utf-8"),
    ) == before


def test_normal_when_global_included(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    serve: Callable[..., Any],
) -> None:
    """ユーザー全体の索引の `paths` の当たらないエントリも分けて受け取り、件数には数えない（正常シナリオ）。"""
    # 準備
    project_index, global_index, project_rule, global_rule = _unmatched_environment(
        e2e_project, make_text_file, make_rule
    )
    before = (project_index.read_text(encoding="utf-8"), global_index.read_text(encoding="utf-8"))
    server = serve(project_index, global_indexes=[global_index])
    # 実行
    result = server.call(
        "check_indexes", project_dir=str(e2e_project), include_global=True, format="json"
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert [
        (entry["position"], entry["rule"]) for entry in reports["project"]["unmatched_paths"]
    ] == [(1, str(project_rule))]
    assert reports["global"]["index"] == str(global_index)
    assert [
        (entry["position"], entry["rule"]) for entry in reports["global"]["unmatched_paths"]
    ] == [(0, str(global_rule))]
    assert content["problem_count"] == 1
    assert (
        project_index.read_text(encoding="utf-8"),
        global_index.read_text(encoding="utf-8"),
    ) == before


def test_normal_when_tag_pattern_unused(
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    start_dev_docs: Callable[..., str],
    serve: Callable[..., Any],
) -> None:
    """使われているどのタグにも当たらないタグのパターンを、索引の場所とエントリの位置つきで受け取る（正常シナリオ）。"""
    # 準備
    dev_docs_url = start_dev_docs(
        {
            "total_count": 3,
            "groups": [{"value": "python", "count": 2}, {"value": "mcp", "count": 1}],
        }
    )
    rule = make_rule("a.md", "# a\n")
    index = make_text_file(
        "rules.yaml",
        f"rules:\n"
        f"  - rule: {rule}\n"
        f"    args:\n"
        f'      filter[tags]: ["re:^python"]\n'
        f"  - rule: {rule}\n"
        f"    args:\n"
        f'      filter[tags]: ["re:^rust"]\n',
    )
    before = index.read_text(encoding="utf-8")
    server = serve(index, dev_docs_url=dev_docs_url)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    report = content["indexes"][0]
    assert report["index"] == str(index)
    assert [(entry["position"], entry["pattern"]) for entry in report["unused_tag_patterns"]] == [
        (1, "re:^rust")
    ]
    assert content["tag_check"] == {"state": "checked", "reason": None}
    assert index.read_text(encoding="utf-8") == before


def test_error_when_dev_docs_unreachable(
    tmp_path: Path,
    e2e_project: Path,
    make_text_file: Callable[..., Path],
    make_rule: Callable[..., Path],
    free_port: Callable[[], int],
    serve: Callable[..., Any],
) -> None:
    """dev-docs に届かないとき、タグの確かめを飛ばした理由とほかの問題を、エラーなしで受け取る（異常シナリオ）。"""
    # 準備
    dev_docs_url = f"http://127.0.0.1:{free_port()}/mcp"
    rule = make_rule("a.md", "# a\n")
    missing = tmp_path / "rules" / "missing.md"
    index = make_text_file(
        "rules.yaml",
        f"rules:\n"
        f"  - rule: {rule}\n"
        f"    args:\n"
        f'      filter[tags]: ["re:^python"]\n'
        f"  - rule: {rule}\n"
        f"    args:\n"
        f'      filter[tags]: ["re:^rust"]\n'
        f"  - rule: {missing}\n",
    )
    server = serve(index, dev_docs_url=dev_docs_url)
    # 実行
    result = server.call("check_indexes", project_dir=str(e2e_project), format="json")
    # 検証
    content = result.structured_content
    report = content["indexes"][0]
    assert result.is_error is False
    assert content["tag_check"]["state"] == "skipped"
    assert dev_docs_url in content["tag_check"]["reason"]
    assert "接続できない" in content["tag_check"]["reason"]
    assert report["unused_tag_patterns"] == []
    assert report["missing_rules"] == [{"position": 2, "rule": str(missing)}]
