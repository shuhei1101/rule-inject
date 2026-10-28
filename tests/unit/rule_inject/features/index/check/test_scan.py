"""features/index/check/scan.py の単体テスト。"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

# `src/app.py` に当たるエントリ（位置 0）と、どのファイルにも当たらないエントリ（位置 1）
INDEX_PY_TOML = (
    "rules:\n"
    "  - rule: /r/py.md\n"
    '    paths: ["**/*.py"]\n'
    "  - rule: /r/toml.md\n"
    '    paths: ["**/*.toml"]\n'
)
# `docs/readme.md` に当たるエントリ（位置 0）を先頭に足した索引
INDEX_MD_PY_TOML = (
    "rules:\n"
    "  - rule: /r/md.md\n"
    '    paths: ["**/*.md"]\n'
    "  - rule: /r/py.md\n"
    '    paths: ["**/*.py"]\n'
    "  - rule: /r/toml.md\n"
    '    paths: ["**/*.toml"]\n'
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """辿るプロジェクトの直下。"""
    path = tmp_path / "project"
    path.mkdir()
    return path


@pytest.fixture
def make_files(project: Path) -> Callable[..., None]:
    """プロジェクトの下に空のファイルを置く factory。"""

    def _make(*names: str) -> None:
        """names の相対パスのファイルを、フォルダごと作って置く。"""
        for name in names:
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")

    return _make


@pytest.fixture
def read_contents(make_index: Callable[..., Path]) -> Callable[..., list[Any]]:
    """索引の YAML を書き、読み取り結果（IndexContent）の並びを返す factory。"""

    def _read(*texts: str) -> list[Any]:
        """texts を索引ごとのファイルに書き、`read_index` で読む。"""
        from rule_inject.features.index import read_index

        return [
            read_index(str(make_index(text, f"index{number}.yaml")), {})
            for number, text in enumerate(texts)
        ]

    return _read


@pytest.fixture
def ticking_clock() -> Callable[[], float]:
    """呼ぶたびに 1 進む時計。"""
    ticks = itertools.count()
    return lambda: float(next(ticks))


def test_scan_unmatched(
    project: Path,
    make_files: Callable[..., None],
    read_contents: Callable[..., list[Any]],
) -> None:
    """どのファイルにも当たらないエントリを返す（正常系）。"""
    from rule_inject.features.index.check.scan import scan_unmatched

    # 準備
    make_files("src/app.py")
    contents = read_contents(INDEX_PY_TOML)
    # 実行
    result = scan_unmatched(str(project), contents, cursor=None, time_limit=30)
    # 検証
    problems = result.checks[0].problems
    assert result.completed is True
    assert result.next_cursor is None
    assert result.scanned_files == 1
    assert result.checks[0].index == contents[0].path
    assert [
        (problem.kind, problem.location, problem.position, problem.reason) for problem in problems
    ] == [("unmatched_path", "rules[1].paths", 1, "/r/toml.md")]
    assert problems[0].rev == contents[0].outcomes[1].rev


def test_scan_unmatched_when_no_paths(
    project: Path,
    make_files: Callable[..., None],
    read_contents: Callable[..., list[Any]],
) -> None:
    """`paths` を持たないエントリと効いていないエントリは確かめない（正常系）。"""
    from rule_inject.features.index.check.scan import scan_unmatched

    # 準備
    make_files("src/app.py")
    contents = read_contents(
        "rules:\n"
        "  - rule: /r/tool.md\n"
        '    tools: ["mcp__*__get_doc"]\n'
        "  - rule: /r/off.md\n"
        '    paths: ["**/*.rs"]\n'
        "    enabled: false\n"
    )
    # 実行
    result = scan_unmatched(str(project), contents, cursor=None, time_limit=30)
    # 検証
    assert result.completed is True
    assert result.checks[0].problems == ()


def test_scan_unmatched_when_time_limit(
    project: Path,
    make_files: Callable[..., None],
    read_contents: Callable[..., list[Any]],
    ticking_clock: Callable[[], float],
) -> None:
    """時間の上限を超えたら続きの位置を返す（正常系）。"""
    from rule_inject.features.index.check.scan import scan_unmatched

    # 準備
    make_files("docs/readme.md", "src/app.py")
    contents = read_contents(INDEX_PY_TOML)
    # 実行
    result = scan_unmatched(str(project), contents, cursor=None, time_limit=0, clock=ticking_clock)
    # 検証
    assert result.completed is False
    assert result.scanned_files == 1
    assert result.next_cursor is not None
    assert result.next_cursor.last_file == "docs/readme.md"
    assert all(check.problems == () for check in result.checks)


def test_scan_unmatched_when_cursor(
    project: Path,
    make_files: Callable[..., None],
    read_contents: Callable[..., list[Any]],
    ticking_clock: Callable[[], float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """続きの位置から辿り、前に当たったエントリは確かめ直さない（正常系）。"""
    from rule_inject.features.index.check import scan
    from rule_inject.features.index.check.scan import scan_unmatched

    # 準備
    make_files("docs/readme.md", "src/app.py")
    contents = read_contents(INDEX_MD_PY_TOML)
    first = scan_unmatched(str(project), contents, cursor=None, time_limit=0, clock=ticking_clock)
    walked: list[str] = []
    real_iter = scan._iter_project_files

    def _spy(project_dir: str, after: str | None) -> Iterator[str]:
        """辿ったファイルを控えながら、本物の列挙を返す。"""
        for relative in real_iter(project_dir, after):
            walked.append(relative)
            yield relative

    monkeypatch.setattr(scan, "_iter_project_files", _spy)
    # 実行
    result = scan_unmatched(str(project), contents, cursor=first.next_cursor, time_limit=30)
    # 検証
    assert result.completed is True
    assert result.scanned_files == 2
    assert result.next_cursor is None
    assert walked == ["src/app.py"]
    assert [problem.location for problem in result.checks[0].problems] == ["rules[2].paths"]


def test_scan_unmatched_when_fingerprint_changed(
    project: Path,
    make_files: Callable[..., None],
    read_contents: Callable[..., list[Any]],
) -> None:
    """エントリの一覧が変わっていたら最初から辿る（正常系）。"""
    from rule_inject.features.index.check.scan import scan_unmatched
    from rule_inject.features.index.check.types import ScanCursor

    # 準備
    make_files("docs/readme.md", "src/app.py")
    contents = read_contents(INDEX_PY_TOML)
    stale = ScanCursor(
        last_file="docs/readme.md",
        scanned_files=1,
        unmatched=((contents[0].path, 0, contents[0].outcomes[0].rev),),
        fingerprint="stale",
    )
    # 実行
    result = scan_unmatched(str(project), contents, cursor=stale, time_limit=30)
    # 検証
    assert result.completed is True
    assert result.scanned_files == 2
    assert [problem.location for problem in result.checks[0].problems] == ["rules[1].paths"]


def test_iter_project_files(project: Path, make_files: Callable[..., None]) -> None:
    """部分ごとの名前の順に返し、`.git` には入らない（正常系）。"""
    from rule_inject.features.index.check.scan import _iter_project_files

    # 準備
    make_files("b.txt", "a/z.txt", ".git/HEAD")
    # 実行
    result = list(_iter_project_files(str(project), None))
    # 検証
    assert result == ["a/z.txt", "b.txt"]


def test_iter_project_files_when_after(project: Path, make_files: Callable[..., None]) -> None:
    """`after` より後だけを返す（正常系）。"""
    from rule_inject.features.index.check.scan import _iter_project_files

    # 準備
    make_files("b.txt", "a/z.txt", ".git/HEAD")
    # 実行
    result = list(_iter_project_files(str(project), "a/z.txt"))
    # 検証
    assert result == ["b.txt"]
