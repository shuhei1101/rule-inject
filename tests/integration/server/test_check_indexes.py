"""インターフェース定義『索引のチェック』の結合テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

# 位置 0 は `src/app.py` に当たり、位置 1・2・3 はどのファイルにも当たらず、位置 4 は無効
FIVE_ENTRIES = (
    "rules:\n"
    "  - rule: {rule}\n"
    '    paths: ["**/*.py"]\n'
    "  - rule: {rule}\n"
    '    paths: ["**/*.rs"]\n'
    "  - rule: {rule}\n"
    '    paths: ["**/config"]\n'
    "  - rule: {rule}\n"
    '    paths: ["**/*.py"]\n'
    '    exclude: ["**/src/**"]\n'
    "  - rule: {rule}\n"
    '    paths: ["**/*.go"]\n'
    "    enabled: false\n"
)


def test_normal_when_no_violation(
    project_dir: Path,
    make_index: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_server: Callable[..., Any],
) -> None:
    """問題の無い索引で `problem_count` が 0 になる（正常系）。"""
    # 準備
    make_project_files("src/app.py")
    first = make_index("# a\n", "rules/a.md")
    second = make_index("# b\n", "rules/b.md")
    index = make_index(
        f'rules:\n  - rule: {first}\n    paths: ["**/*.py"]\n  - rule: {second}\n    on: [write]\n'
    )
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["problem_count"] == 0
    assert content["indexes"][0]["index"] == str(index)
    assert content["indexes"][0]["hook_error"] is None
    assert content["indexes"][0]["violations"] == []
    assert content["indexes"][0]["missing_rules"] == []
    assert content["indexes"][0]["skipped_entries"] == []
    assert content["indexes"][0]["unmatched_paths"] == []
    assert content["unmatched_scan"]["completed"] is True
    assert content["config_path"] == str(server.config_path)


def test_normal_when_schema_violated(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """フックは読めるが Schema に違反するエントリの場所と理由を返す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n    paths: []\n  - rule: {rule}\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert report["violations"][0]["location"] == "rules[0].paths"
    assert report["violations"][0]["reason"]
    assert report["hook_error"] is None


def test_normal_when_unreadable_by_hook(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """フックが読めない索引は理由だけを返し、Schema には照らさない（正常系）。"""
    # 準備
    index = make_index("rules:\n  - rule: /r/a.md\n    paths: [a,\n      b]\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    report = result.structured_content["indexes"][0]
    assert "行目" in report["hook_error"]
    assert report["violations"] == []
    assert report["missing_rules"] == []


def test_normal_when_rule_file_missing(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
) -> None:
    """ルールの場所にファイルが無いエントリを返す（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f"rules:\n  - rule: {rule}\n  - rule: {tmp_path}/rules/missing.md\n")
    server = running_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["indexes"][0]["missing_rules"] == [
        {"position": 1, "rule": f"{tmp_path}/rules/missing.md"}
    ]
    assert content["problem_count"] == 1


def test_error_when_project_dir_not_absolute(
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """相対パスの `project_dir` をエラーにする（異常系）。"""
    # 準備
    server = running_server(make_index("rules: []\n"))
    # 実行
    result = server.call("check_indexes", project_dir="project", format="json")
    # 検証
    assert result.is_error is True
    assert "絶対パス" in text_of(result)


def test_error_when_settings_unreadable(
    project_dir: Path,
    make_index: Callable[..., Path],
    running_server: Callable[..., Any],
    invalid_config: Callable[[], str],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """呼び出しの時点で読めない設定ファイルをエラーにする（異常系）。"""
    # 準備
    server = running_server(make_index("rules: []\n"))
    config = invalid_config()
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    assert result.is_error is True
    assert config in text_of(result)
    assert "foo" in text_of(result)


def test_normal_when_paths_unmatched(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """プロジェクトの索引の `paths` の当たらないエントリを返し、ユーザー全体の索引の分は返さない（正常系）。"""
    # 準備
    rule = rule_file("project.md")
    global_rule = rule_file("global.md")
    make_project_files("src/app.py", ".git/config")
    project_index = make_index(FIVE_ENTRIES.format(rule=rule), "project.yaml")
    global_index = make_index(
        f'rules:\n  - rule: {global_rule}\n    paths: ["**/*.java"]\n', "global.yaml"
    )
    server = running_server(project_index, global_indexes=[global_index])
    # 並びは、ユーザー全体の索引の 1 件の後にプロジェクトの索引の効いているエントリ（位置 0〜3）
    revs = list_revs(server)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert reports["project"]["unmatched_paths"] == [
        {"position": 1, "rev": revs[2], "rule": str(rule)},
        {"position": 2, "rev": revs[3], "rule": str(rule)},
        {"position": 3, "rev": revs[4], "rule": str(rule)},
    ]
    assert reports["global"]["unmatched_paths"] == []
    assert content["problem_count"] == 3
    assert content["unmatched_scan"]["completed"] is True
    assert content["unmatched_scan"]["scanned_files"] == 1


def test_normal_when_global_included(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_server: Callable[..., Any],
    list_revs: Callable[[Any], list[str]],
) -> None:
    """`include_global` が `true` のとき、ユーザー全体の索引の `paths` の当たらないエントリも返し、`problem_count` には数えない（正常系）。"""
    # 準備
    rule = rule_file("project.md")
    global_rule = rule_file("global.md")
    make_project_files("src/app.py", ".git/config")
    project_index = make_index(FIVE_ENTRIES.format(rule=rule), "project.yaml")
    global_index = make_index(
        f'rules:\n  - rule: {global_rule}\n    paths: ["**/*.java"]\n', "global.yaml"
    )
    server = running_server(project_index, global_indexes=[global_index])
    revs = list_revs(server)
    # 実行
    result = server.call(
        "check_indexes", project_dir=str(project_dir), include_global=True, format="json"
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert reports["global"]["unmatched_paths"] == [
        {"position": 0, "rev": revs[0], "rule": str(global_rule)}
    ]
    assert [entry["position"] for entry in reports["project"]["unmatched_paths"]] == [1, 2, 3]
    assert content["problem_count"] == 3


def test_normal_when_scan_timed_out(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_limited_server: Callable[..., Any],
) -> None:
    """上限を超えたら辿るのをやめ、`paths` の当たらないエントリを返さずに、終えられなかったことと続きの位置を返す（正常系）。"""
    # 準備
    rule = rule_file("project.md")
    make_project_files("docs/readme.md", "src/app.py")
    missing = tmp_path / "rules" / "missing.md"
    index = make_index(FIVE_ENTRIES.format(rule=rule) + f"  - rule: {missing}\n")
    server = running_limited_server(index)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    scan = content["unmatched_scan"]
    assert scan["completed"] is False
    assert "秒" in scan["reason"]
    assert "cursor" in scan["reason"]
    assert scan["scanned_files"] == 1
    assert scan["next_cursor"] is not None
    assert content["indexes"][0]["unmatched_paths"] == []
    assert content["indexes"][0]["missing_rules"] == [{"position": 5, "rule": str(missing)}]
    assert content["problem_count"] == 1


def test_normal_when_cursor_passed(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_limited_server: Callable[..., Any],
) -> None:
    """前の呼び出しの `next_cursor` を渡すと続きから辿り、最後まで辿れたら 1 回で辿ったときと同じ `paths` の当たらないエントリを返す（正常系）。"""
    # 準備
    rule = rule_file("project.md")
    make_project_files("docs/readme.md", "src/app.py")
    index = make_index(FIVE_ENTRIES.format(rule=rule))
    server = running_limited_server(index)
    first = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 実行
    second = server.call(
        "check_indexes",
        project_dir=str(project_dir),
        cursor=first.structured_content["unmatched_scan"]["next_cursor"],
        format="json",
    )
    # 検証
    content = second.structured_content
    assert content["unmatched_scan"]["completed"] is True
    assert content["unmatched_scan"]["next_cursor"] is None
    assert content["unmatched_scan"]["scanned_files"] == 2
    assert [entry["position"] for entry in content["indexes"][0]["unmatched_paths"]] == [1, 2, 3]
    assert content["problem_count"] == 3


def test_normal_when_index_changed_since_cursor(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_limited_server: Callable[..., Any],
) -> None:
    """`cursor` を返した後に索引のエントリが変わったら、`cursor` を使わず最初のファイルから辿り直す（正常系）。"""
    # 準備
    rule = rule_file("project.md")
    make_project_files("docs/readme.md", "src/app.py")
    index = make_index(FIVE_ENTRIES.format(rule=rule))
    server = running_limited_server(index)
    first = server.call("check_indexes", project_dir=str(project_dir), format="json")
    index.write_text(index.read_text(encoding="utf-8").replace("*.rs", "*.toml"), encoding="utf-8")
    # 実行
    second = server.call(
        "check_indexes",
        project_dir=str(project_dir),
        cursor=first.structured_content["unmatched_scan"]["next_cursor"],
        format="json",
    )
    # 検証
    first_scan = first.structured_content["unmatched_scan"]
    second_scan = second.structured_content["unmatched_scan"]
    assert second_scan["scanned_files"] == 1
    assert second_scan["completed"] is False
    assert second_scan["next_cursor"] != first_scan["next_cursor"]


def test_error_when_cursor_invalid(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    make_project_files: Callable[..., None],
    running_limited_server: Callable[..., Any],
    text_of: Callable[[CallToolResult], str],
) -> None:
    """読めない `cursor` と、別の `project_dir` で返した `cursor` をエラーにする（異常系）。"""
    # 準備
    rule = rule_file("project.md")
    make_project_files("docs/readme.md", "src/app.py")
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    index = make_index(FIVE_ENTRIES.format(rule=rule))
    server = running_limited_server(index)
    issued = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 実行
    unreadable = server.call(
        "check_indexes", project_dir=str(project_dir), cursor="not-a-cursor", format="json"
    )
    mismatched = server.call(
        "check_indexes",
        project_dir=str(other_dir),
        cursor=issued.structured_content["unmatched_scan"]["next_cursor"],
        format="json",
    )
    # 検証
    assert unreadable.is_error is True
    assert "cursor" in text_of(unreadable)
    assert mismatched.is_error is True
    assert "cursor" in text_of(mismatched)


def test_normal_when_tag_pattern_unused(
    project_dir: Path,
    make_index: Callable[..., Path],
    start_fake_dev_docs: Callable[..., Any],
    running_server: Callable[..., Any],
) -> None:
    """dev-docs の使われているタグに当たらないタグのパターンを、全ての索引について返し、`problem_count` には数えない（正常系）。"""
    # 準備
    fake = start_fake_dev_docs(
        {
            "total_count": 3,
            "groups": [{"value": "Python", "count": 2}, {"value": "mcp", "count": 1}],
        }
    )
    rule = make_index("# a\n", "rules/a.md")
    project_index = make_index(
        "rules:\n"
        f"  - rule: {rule}\n"
        "    args:\n"
        '      filter[tags]: ["python"]\n'
        f"  - rule: {rule}\n"
        "    args:\n"
        '      filter[tags]: ["pyhton", "m*"]\n'
        f"  - rule: {rule}\n"
        "    read_by:\n"
        '      - tools: ["*search_docs"]\n'
        "        args:\n"
        '          filter[tags]: ["rust"]\n'
        f"  - rule: {rule}\n"
        "    args:\n"
        '      filter.tags: ["go"]\n'
        f"  - rule: {rule}\n"
        "    enabled: false\n"
        "    args:\n"
        '      filter[tags]: ["java"]\n',
        "project.yaml",
    )
    global_index = make_index(
        f'rules:\n  - rule: {rule}\n    args:\n      filter[tags]: ["re:^kotlin$"]\n',
        "global.yaml",
    )
    server = running_server(project_index, global_indexes=[global_index], dev_docs_url=fake.url)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert [
        (entry["position"], entry["location"], entry["key"], entry["pattern"])
        for entry in reports["project"]["unused_tag_patterns"]
    ] == [
        (1, "args", "filter[tags]", "pyhton"),
        (2, "read_by[0].args", "filter[tags]", "rust"),
    ]
    assert all(entry["rev"] for entry in reports["project"]["unused_tag_patterns"])
    assert [
        (entry["position"], entry["location"], entry["key"], entry["pattern"])
        for entry in reports["global"]["unused_tag_patterns"]
    ] == [(0, "args", "filter[tags]", "re:^kotlin$")]
    assert content["tag_check"] == {"state": "checked", "reason": None}
    assert content["problem_count"] == 0
    assert fake.calls() == [
        {"source": "*", "group_by": "tags", "format": "json", "cwd": str(project_dir)}
    ]


def test_normal_when_dev_docs_unreachable(
    tmp_path: Path,
    project_dir: Path,
    make_index: Callable[..., Path],
    free_port: Callable[[], int],
    running_server: Callable[..., Any],
) -> None:
    """dev-docs に接続できないときは、タグの確かめだけを飛ばして理由を返し、ツールのエラーにしない（正常系）。"""
    # 準備
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(
        "rules:\n"
        f"  - rule: {rule}\n"
        "    args:\n"
        '      filter[tags]: ["python"]\n'
        f"  - rule: {tmp_path}/rules/missing.md\n"
    )
    url = f"http://127.0.0.1:{free_port()}/mcp"
    server = running_server(index, dev_docs_url=url)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    report = content["indexes"][0]
    assert content["success"] is True
    assert content["tag_check"]["state"] == "skipped"
    assert url in content["tag_check"]["reason"]
    assert "接続できない" in content["tag_check"]["reason"]
    assert report["unused_tag_patterns"] == []
    assert len(report["missing_rules"]) == 1
    assert content["problem_count"] == 1


def test_normal_when_dev_docs_returns_nothing(
    project_dir: Path,
    make_index: Callable[..., Path],
    start_fake_dev_docs: Callable[..., Any],
    running_server: Callable[..., Any],
) -> None:
    """dev-docs が読める文書を 0 件と返したときは、タグの確かめを飛ばして理由を返す（正常系）。"""
    # 準備
    fake = start_fake_dev_docs({"total_count": 0, "returned": 0})
    rule = make_index("# a\n", "rules/a.md")
    index = make_index(f'rules:\n  - rule: {rule}\n    args:\n      filter[tags]: ["python"]\n')
    server = running_server(index, dev_docs_url=fake.url)
    # 実行
    result = server.call("check_indexes", project_dir=str(project_dir), format="json")
    # 検証
    content = result.structured_content
    assert content["tag_check"]["state"] == "skipped"
    assert "0 件" in content["tag_check"]["reason"]
    assert content["indexes"][0]["unused_tag_patterns"] == []
    assert [call["cwd"] for call in fake.calls()] == [str(project_dir)]
