"""features/index/edit/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from rule_inject.features.index._yaml import parse_index

INDEX_TEXT = (
    "# ルールの索引\n"
    "default_on: [write]  # 既定\n"
    "rules:\n"
    "  # python のルール\n"
    "  - rule: 'python.md'\n"
    '    paths: ["**/*.py"]\n'
    '    exclude: ["**/gen/**"]\n'
    "  # ts のルール\n"
    '  - rule: "ts.md"\n'
    '    paths: ["**/*.ts"]\n'
    "    on: [write]\n"
)

DELETE_TEXT = (
    "rules:\n"
    "  # a のコメント\n"
    "  - rule: a.md  # a の行末\n"
    '    paths: ["**/*.py"]\n'
    "  # b のコメント\n"
    "  - rule: b.md\n"
    "    # b の中\n"
    '    paths: ["**/*.ts"]\n'
    "  # c のコメント\n"
    "  - rule: c.md\n"
    '    paths: ["**/*.go"]\n'
    "default_on: [write]\n"
)

CheckSpy = tuple[Callable[..., tuple[str, ...]], list[tuple[Any, ...]]]


@pytest.fixture
def locks() -> Any:
    """索引ごとのロック。"""
    from rule_inject.features.index.edit import IndexLocks

    return IndexLocks()


@pytest.fixture
def make_check() -> Callable[..., CheckSpy]:
    """呼ばれた引数を控え、決めた行を返す書き込みのチェックを作る factory。"""

    def _make(lines: Sequence[str] = ()) -> CheckSpy:
        """lines を返し、呼ばれた引数を calls に控える関数と calls を返す。"""
        calls: list[tuple[Any, ...]] = []

        def _check(*args: Any) -> tuple[str, ...]:
            """引数を控えて lines を返す。"""
            calls.append(args)
            return tuple(lines)

        return _check, calls

    return _make


@pytest.fixture
def write(locks: Any) -> Callable[..., Any]:
    """`write_entry` を、使わない引数を既定にして呼ぶ関数。"""
    from rule_inject.features.index.edit import write_entry

    def _write(
        index: Path,
        entry: dict[str, Any],
        check: Callable[..., tuple[str, ...]],
        *,
        position: int | None = None,
        expected_rev: str | None = None,
        remove_keys: Sequence[str] = (),
        dry_run: bool = False,
    ) -> Any:
        """索引にエントリを書き込む。"""
        return write_entry(
            str(index),
            entry,
            position=position,
            expected_rev=expected_rev,
            remove_keys=remove_keys,
            dry_run=dry_run,
            locks=locks,
            check_change=check,
        )

    return _write


def test_write_entry_when_new(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """末尾に新規作成し、他の行を変えない（正常系）。"""
    from rule_inject.features.index import read_index

    # 準備
    index = make_index(INDEX_TEXT)
    check, _ = make_check()
    # 実行
    result = write(index, {"rule": "new.md", "paths": ["**/*.go"], "on": ["write"]}, check)
    # 検証
    after = index.read_text(encoding="utf-8")
    appended = after[len(INDEX_TEXT) :].splitlines()
    assert after.startswith(INDEX_TEXT)
    assert len(appended) == 3
    assert appended[0] == "  - rule: new.md"
    assert appended[1].startswith("    paths: [")
    assert appended[1].endswith("]")
    assert result.position == 2
    assert result.written is True
    assert result.rev == read_index(str(index), {}).outcomes[2].rev


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("default_on: [write]\n", id="no_rules"),
        pytest.param("rules:\n", id="empty_rules"),
    ],
)
def test_write_entry_when_no_rules(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
    text: str,
) -> None:
    """`rules` が無いか値が空の索引では `rules` をブロックのリストにする（正常系）。"""
    # 準備
    index = make_index(text)
    check, _ = make_check()
    # 実行
    result = write(index, {"rule": "new.md"}, check)
    # 検証
    after = index.read_text(encoding="utf-8")
    assert "rules:\n  - rule: new.md\n" in after
    assert result.position == 0
    assert parse_index(after)[1] == [{"rule": "new.md"}]


def test_write_entry_when_update(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """渡したキーだけを書き換え、`remove_keys` を削除する（正常系）。"""
    from rule_inject.features.index import entry_revs

    # 準備
    index = make_index(INDEX_TEXT)
    check, _ = make_check()
    expected_rev = entry_revs(INDEX_TEXT)[0]
    # 実行
    write(
        index,
        {"paths": ["**/*.rs"], "on": ["read"]},
        check,
        position=0,
        expected_rev=expected_rev,
        remove_keys=["exclude"],
    )
    # 検証
    before_lines = INDEX_TEXT.splitlines()
    after_lines = index.read_text(encoding="utf-8").splitlines()
    removed = [line for line in before_lines if line not in after_lines]
    assert removed == ['    paths: ["**/*.py"]', '    exclude: ["**/gen/**"]']
    assert "    on: [read]" in after_lines
    assert "  - rule: 'python.md'" in after_lines
    assert "  # python のルール" in after_lines
    assert after_lines[-4:] == before_lines[-4:]


def test_write_entry_when_dry_run(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """`dry_run` は差分だけを返して書き換えない（正常系）。"""
    # 準備
    index = make_index(INDEX_TEXT)
    before = index.read_bytes()
    check, _ = make_check()
    # 実行
    result = write(index, {"rule": "new.md"}, check, dry_run=True)
    # 検証
    assert result.written is False
    assert "new.md" in result.diff
    assert index.read_bytes() == before


def test_write_entry_when_rev_mismatch(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """バージョンが合わなければ書き込まない（異常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(INDEX_TEXT)
    before = index.read_bytes()
    check, _ = make_check()
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        write(index, {"paths": ["**/*.rs"]}, check, position=0, expected_rev="000000000000")
    assert entry_revs(INDEX_TEXT)[0] in raised.value.reason
    assert index.read_bytes() == before


def test_write_entry_when_position_missing(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """無い位置へは書き込まない（異常系）。"""
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(INDEX_TEXT)
    check, _ = make_check()
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        write(index, {"on": ["read"]}, check, position=2, expected_rev="000000000000")
    assert "2" in raised.value.reason


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("rules:\n  - rule: a.md\n    paths: [x\n", id="unclosed_flow"),
        pytest.param("- rule: a.md\n", id="top_level_list"),
    ],
)
def test_write_entry_when_unparsable(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
    text: str,
) -> None:
    """YAML として読めない索引には書き込まない（異常系）。"""
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(text)
    check, _ = make_check()
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        write(index, {"rule": "new.md"}, check)
    assert raised.value.path == str(index)
    assert index.read_text(encoding="utf-8") == text


def test_write_entry_when_check_fails(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """新しい問題が出るときは書き込まない（異常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(INDEX_TEXT)
    before = index.read_bytes()
    check, calls = make_check(["rules[2].paths: 空のリスト", "rules[2].on: 空のリスト"])
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        write(index, {"rule": "new.md", "paths": []}, check)
    assert "rules[2].paths: 空のリスト" in raised.value.reason
    assert "rules[2].on: 空のリスト" in raised.value.reason
    assert index.read_bytes() == before
    index_path, before_text, after_text, changed_rev = calls[0]
    assert index_path == str(index)
    assert before_text == INDEX_TEXT
    assert changed_rev == entry_revs(after_text)[2]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('rules:\n  - rule: "a\\tb.md"\n', id="escaped_double_quote"),
        pytest.param("rules:\n  - rule: b.md\n    paths: [010, 0x1F, 1e3]\n", id="numbers"),
        pytest.param("rules:\n  - rule: c.md\n    paths: [~, null]\n", id="null_like"),
    ],
)
def test_write_entry_when_scalar_notation(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
    text: str,
) -> None:
    """書き方によらず一覧のバージョンで書き換えられる（正常系）。"""
    from rule_inject.features.index import read_index

    # 準備
    index = make_index(text)
    check, calls = make_check()
    expected_rev = read_index(str(index), {}).outcomes[0].rev
    # 実行
    result = write(index, {"on": ["read"]}, check, position=0, expected_rev=expected_rev)
    # 検証
    assert result.written is True
    assert result.rev == read_index(str(index), {}).outcomes[0].rev
    assert calls[0][3] == result.rev


def test_write_entry_when_hook_unreadable(
    make_index: Callable[..., Path],
    make_check: Callable[..., CheckSpy],
    write: Callable[..., Any],
) -> None:
    """フックが読めない索引のエントリは書き換えない（異常系）。"""
    from rule_inject.shared.errors import IndexEditError

    # 準備
    text = "rules:\n  - rule: a.md\n    on: [foo]\n"
    index = make_index(text)
    check, _ = make_check()
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        write(index, {"on": ["read"]}, check, position=0, expected_rev="000000000000")
    assert "2行目" in raised.value.reason
    assert index.read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    ("position", "rule", "expected"),
    [
        pytest.param(
            0,
            "a.md",
            "rules:\n"
            "  # b のコメント\n"
            "  - rule: b.md\n"
            "    # b の中\n"
            '    paths: ["**/*.ts"]\n'
            "  # c のコメント\n"
            "  - rule: c.md\n"
            '    paths: ["**/*.go"]\n'
            "default_on: [write]\n",
            id="first",
        ),
        pytest.param(
            1,
            "b.md",
            "rules:\n"
            "  # a のコメント\n"
            "  - rule: a.md  # a の行末\n"
            '    paths: ["**/*.py"]\n'
            "  # c のコメント\n"
            "  - rule: c.md\n"
            '    paths: ["**/*.go"]\n'
            "default_on: [write]\n",
            id="middle",
        ),
        pytest.param(
            2,
            "c.md",
            "rules:\n"
            "  # a のコメント\n"
            "  - rule: a.md  # a の行末\n"
            '    paths: ["**/*.py"]\n'
            "  # b のコメント\n"
            "  - rule: b.md\n"
            "    # b の中\n"
            '    paths: ["**/*.ts"]\n'
            "default_on: [write]\n",
            id="last",
        ),
    ],
)
def test_delete_entry(
    make_index: Callable[..., Path],
    locks: Any,
    position: int,
    rule: str,
    expected: str,
) -> None:
    """対象のエントリとそのコメントだけを除き、前後のエントリのコメントを残す（正常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.features.index.edit import delete_entry

    # 準備
    index = make_index(DELETE_TEXT)
    expected_rev = entry_revs(DELETE_TEXT)[position]
    # 実行
    result = delete_entry(
        str(index), position=position, expected_rev=expected_rev, dry_run=False, locks=locks
    )
    # 検証
    after = index.read_text(encoding="utf-8")
    assert after == expected
    assert result.rule == rule
    assert result.written is True
    assert len(parse_index(after)[1]) == 2


def test_delete_entry_when_only_entry(make_index: Callable[..., Path], locks: Any) -> None:
    """唯一のエントリを削除すると `rules:` だけが残る（正常系）。"""
    from rule_inject.features.index import entry_revs
    from rule_inject.features.index.edit import delete_entry

    # 準備
    text = "rules:\n  - rule: a.md\n    paths: [x]\n"
    index = make_index(text)
    expected_rev = entry_revs(text)[0]
    # 実行
    delete_entry(str(index), position=0, expected_rev=expected_rev, dry_run=False, locks=locks)
    # 検証
    after = index.read_text(encoding="utf-8")
    assert after == "rules:\n"
    assert parse_index(after)[1] == []


def test_delete_entry_when_rev_mismatch(make_index: Callable[..., Path], locks: Any) -> None:
    """バージョンが合わなければ削除しない（異常系）。"""
    from rule_inject.features.index.edit import delete_entry
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(DELETE_TEXT)
    before = index.read_bytes()
    # 実行・検証
    with pytest.raises(IndexEditError):
        delete_entry(
            str(index), position=0, expected_rev="000000000000", dry_run=False, locks=locks
        )
    assert index.read_bytes() == before


@pytest.mark.parametrize(
    ("text", "line"),
    [
        pytest.param("rules:\n  - rule: a.md\n    on: [foo]\n", "2行目", id="invalid_on"),
        pytest.param("rules: [{rule: a.md}, {rule: b.md}]\n", "1行目", id="flow_rules"),
    ],
)
def test_delete_entry_when_hook_unreadable(
    make_index: Callable[..., Path],
    locks: Any,
    text: str,
    line: str,
) -> None:
    """フックが読めない索引からは削除しない（異常系）。"""
    from rule_inject.features.index.edit import delete_entry
    from rule_inject.shared.errors import IndexEditError

    # 準備
    index = make_index(text)
    # 実行・検証
    with pytest.raises(IndexEditError) as raised:
        delete_entry(
            str(index), position=0, expected_rev="000000000000", dry_run=False, locks=locks
        )
    assert line in raised.value.reason
    assert index.read_text(encoding="utf-8") == text
