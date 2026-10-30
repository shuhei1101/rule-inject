"""server/check_tools.py の単体テスト。"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

# 辿る時間の上限（秒）。辿り終えられる値
SCAN_TIME_LIMIT = 30
# dev-docs への問い合わせの待ち時間の上限（秒）。待ち終えられる値
DEV_DOCS_TIMEOUT = 108
# 設定ファイルの `global.dev_docs_url` に書く接続先
DEV_DOCS_URL = "http://docs.example/mcp"


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


@pytest.fixture
def build_tag_env(
    project_dir: Path,
    make_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    server_env: Callable[..., dict[str, str]],
) -> Callable[..., dict[str, str]]:
    """`global.indexes` とプロジェクトの索引に、`pyhton` のパターンを持つエントリを 1 つずつ置いた設定ファイルを指す環境変数を返す factory。"""

    def _make(*, key: str = "filter[tags]", project_extra: str = "") -> dict[str, str]:
        """`args` のキーと、プロジェクトの索引に加えるエントリ（YAML）を指定して環境変数を作る。"""
        global_index = make_index(
            f'rules:\n  - rule: {rule_file("global.md")}\n    args:\n      {key}: ["pyhton"]\n',
            "global.yaml",
        )
        project_index = make_index(
            f'rules:\n  - rule: {rule_file("project.md")}\n    args:\n      {key}: ["pyhton"]\n'
            + project_extra,
            "project.yaml",
        )
        return server_env(
            "global:\n"
            f"  dev_docs_url: {DEV_DOCS_URL}\n"
            "  indexes:\n"
            f"    - {global_index}\n"
            "projects:\n"
            f"  - match: {project_dir}\n"
            "    indexes:\n"
            f"      - {project_index}\n"
        )

    return _make


@pytest.fixture
def stub_fetch_used_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., list[tuple[str, str]]]:
    """`fetch_used_tags` を決めた結果を返す関数に差し替え、受けた接続先と `project_dir` の記録を返す factory。"""

    def _install(tags: tuple[str, ...], reason: str | None) -> list[tuple[str, str]]:
        """tags と reason を持つ `UsedTags` を返す関数に差し替える。"""
        from rule_inject.server.dev_docs import UsedTags

        calls: list[tuple[str, str]] = []

        async def fake(url: str, project_dir: str, **_: float) -> UsedTags:
            """呼び出しを記録して、決めた結果を返す。"""
            calls.append((url, project_dir))
            return UsedTags(tags=tags, reason=reason)

        monkeypatch.setattr("rule_inject.server.check_tools.fetch_used_tags", fake)
        return calls

    return _install


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
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
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
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=unmatched_env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
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
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            include_global=True,
            env=unmatched_env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
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
    first = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=unmatched_env,
            validator=validator,
            scan_time_limit=0,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
    )
    second = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            cursor=first.structured_content["unmatched_scan"]["next_cursor"],
            env=unmatched_env,
            validator=validator,
            scan_time_limit=0,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
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
        asyncio.run(
            check_indexes(
                project_dir=str(project_dir),
                format="json",
                cursor="broken",
                env=unmatched_env,
                validator=load_validator(),
                scan_time_limit=SCAN_TIME_LIMIT,
                dev_docs_timeout=DEV_DOCS_TIMEOUT,
            )
        )


def test_check_indexes_when_tag_unused(
    project_dir: Path,
    build_tag_env: Callable[..., dict[str, str]],
    stub_fetch_used_tags: Callable[..., list[tuple[str, str]]],
) -> None:
    """使われていないタグのパターンを全ての索引に載せ、数えない（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 準備
    calls = stub_fetch_used_tags(("python",), None)
    env = build_tag_env()
    # 実行
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert [
        (entry["position"], entry["location"], entry["key"], entry["pattern"])
        for entry in reports["global"]["unused_tag_patterns"]
    ] == [(0, "args", "filter[tags]", "pyhton")]
    assert [
        (entry["position"], entry["location"], entry["key"], entry["pattern"])
        for entry in reports["project"]["unused_tag_patterns"]
    ] == [(0, "args", "filter[tags]", "pyhton")]
    assert len(reports["project"]["unused_tag_patterns"][0]["rev"]) == 12
    assert content["tag_check"] == {"state": "checked", "reason": None}
    assert content["problem_count"] == 0
    assert calls == [(DEV_DOCS_URL, str(project_dir))]


def test_check_indexes_when_tag_check_skipped(
    project_dir: Path,
    build_tag_env: Callable[..., dict[str, str]],
    stub_fetch_used_tags: Callable[..., list[tuple[str, str]]],
) -> None:
    """dev-docs に届かないときはタグの確かめだけを飛ばす（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 準備
    stub_fetch_used_tags((), "x")
    env = build_tag_env(project_extra="  - rule: /nonexistent/x.md\n")
    # 実行
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
    )
    # 検証
    content = result.structured_content
    reports = {report["origin"]: report for report in content["indexes"]}
    assert content["tag_check"] == {"state": "skipped", "reason": "x"}
    assert reports["global"]["unused_tag_patterns"] == []
    assert reports["project"]["unused_tag_patterns"] == []
    assert len(reports["project"]["missing_rules"]) == 1
    assert content["problem_count"] == 1


def test_check_indexes_when_no_tag_patterns(
    project_dir: Path,
    build_tag_env: Callable[..., dict[str, str]],
    stub_fetch_used_tags: Callable[..., list[tuple[str, str]]],
) -> None:
    """タグのパターンが無ければ dev-docs に問い合わせない（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server.check_tools import check_indexes

    # 準備
    calls = stub_fetch_used_tags(("python",), None)
    env = build_tag_env(key="filter.tags")
    # 実行
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
    )
    # 検証
    assert result.structured_content["tag_check"] == {"state": "no_patterns", "reason": None}
    assert calls == []


def test_check_indexes_when_query_parallel(
    project_dir: Path,
    build_tag_env: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """dev-docs への問い合わせを、ファイルを辿るのと並べて行う（正常系）。"""
    from rule_inject.features.index.check import load_validator
    from rule_inject.server import check_tools
    from rule_inject.server.check_tools import check_indexes
    from rule_inject.server.dev_docs import UsedTags

    # 準備: 問い合わせが始まったら Event を立て、辿る側がそれを待てたかを記録する
    started = threading.Event()
    observed: list[bool] = []
    real_scan = check_tools.scan_unmatched

    async def fake_fetch(url: str, project_dir: str, **_: float) -> UsedTags:
        """呼ばれたら Event を立てて、使われているタグを返す。"""
        started.set()
        return UsedTags(tags=("a",), reason=None)

    def fake_scan(*args: Any, **kwargs: Any) -> Any:
        """問い合わせが始まるのを 5 秒まで待ち、待てたかを記録して本物を呼ぶ。"""
        observed.append(started.wait(5))
        return real_scan(*args, **kwargs)

    monkeypatch.setattr("rule_inject.server.check_tools.fetch_used_tags", fake_fetch)
    monkeypatch.setattr("rule_inject.server.check_tools.scan_unmatched", fake_scan)
    env = build_tag_env()
    # 実行
    result = asyncio.run(
        check_indexes(
            project_dir=str(project_dir),
            format="json",
            env=env,
            validator=load_validator(),
            scan_time_limit=SCAN_TIME_LIMIT,
            dev_docs_timeout=DEV_DOCS_TIMEOUT,
        )
    )
    # 検証
    assert observed == [True]
    assert result.structured_content["tag_check"]["state"] == "checked"


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
