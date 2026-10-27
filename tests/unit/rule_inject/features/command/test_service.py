"""features/command/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from rule_inject.features.command import service
from rule_inject.features.command.service import (
    FULL_READ_COMMANDS,
    READ_COMMANDS,
    extract_read_paths,
)


@pytest.fixture
def make_files(tmp_path: Path) -> Callable[[int], list[str]]:
    """連番の名前のファイルを tmp_path に置き、名前のリストを返す factory。"""

    def _make(count: int) -> list[str]:
        """f000.md から count 件のファイルを置く。"""
        names = [f"f{number:03d}.md" for number in range(count)]
        for name in names:
            (tmp_path / name).write_text("# f\n", encoding="utf-8")
        return names

    return _make


def test_extract_read_paths(tmp_path: Path) -> None:
    """cd とパイプをまたいでパスを取り出す（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print()\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("cd src && cat app.py | head -n 5", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "src" / "app.py")]


def test_extract_read_paths_when_pattern_arg(tmp_path: Path) -> None:
    """実在しない引数を捨てる（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("grep -n foo a.md", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "a.md")]


def test_extract_read_paths_when_not_full_read(tmp_path: Path) -> None:
    """対象外のコマンドは見ない（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("grep foo a.md", tmp_path, FULL_READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_unparsable(tmp_path: Path) -> None:
    """分けられないコマンドは空を返す（正常系）。"""
    # 実行
    result = extract_read_paths('cat "a.md', tmp_path, READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_glob(tmp_path: Path) -> None:
    """引用符の外の glob を展開する（正常系）。"""
    # 準備
    (tmp_path / "src" / "tasks").mkdir(parents=True)
    (tmp_path / "src" / "tasks" / "b.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "src" / "tasks" / "a.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "src" / "tasks" / "c.md").write_text("# c\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("cat src/tasks/*.py", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [
        str(tmp_path / "src" / "tasks" / "a.py"),
        str(tmp_path / "src" / "tasks" / "b.py"),
    ]


def test_extract_read_paths_when_quoted_glob(tmp_path: Path) -> None:
    """引用符の中の glob は展開しない（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print()\n", encoding="utf-8")
    # 実行
    result = extract_read_paths('cat "src/*.py"', tmp_path, READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_glob_no_match(tmp_path: Path) -> None:
    """当たるファイルが無い glob を捨てる（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("print()\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("cat src/*.rs", tmp_path, READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_for_loop(tmp_path: Path) -> None:
    """for の語の並びを読む対象にする（正常系）。"""
    # 準備
    (tmp_path / "src" / "tasks").mkdir(parents=True)
    (tmp_path / "tests" / "unit" / "tasks").mkdir(parents=True)
    (tmp_path / "src" / "tasks" / "text_rules.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "src" / "tasks" / "service.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "tasks" / "test_service.py").write_text(
        "print()\n", encoding="utf-8"
    )
    command = (
        'for f in src/tasks/*.py tests/unit/tasks/test_service.py; do echo "=== $f"; cat "$f"; done'
    )
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [
        str(tmp_path / "src" / "tasks" / "service.py"),
        str(tmp_path / "src" / "tasks" / "text_rules.py"),
        str(tmp_path / "tests" / "unit" / "tasks" / "test_service.py"),
    ]


def test_extract_read_paths_when_for_loop_multiline(tmp_path: Path) -> None:
    """改行で区切った for の語の並びを読む対象にする（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# b\n", encoding="utf-8")
    command = 'for f in a.md b.md\ndo\n  cat "${f}"\ndone'
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "a.md"), str(tmp_path / "b.md")]


def test_extract_read_paths_when_for_loop_not_read(tmp_path: Path) -> None:
    """読むコマンドが変数を取らない for は見ない（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    # 実行
    result = extract_read_paths('for f in a.md; do echo "$f"; done', tmp_path, READ_COMMANDS)
    # 検証
    assert result == []


def test_extract_read_paths_when_for_loop_full_read(tmp_path: Path) -> None:
    """全体を読むコマンドの for と glob を既読の対象にする（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "src" / "b.md").write_text("# b\n", encoding="utf-8")
    command = 'for f in a.md; do cat "$f"; done && cat src/*.md'
    # 実行
    result = extract_read_paths(command, tmp_path, FULL_READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "a.md"), str(tmp_path / "src" / "b.md")]


def test_extract_read_paths_when_newline(tmp_path: Path) -> None:
    """改行をコマンドの区切りにする（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print()\n", encoding="utf-8")
    # 実行
    result = extract_read_paths("cd src\ncat app.py", tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "src" / "app.py")]


def test_extract_read_paths_when_line_continuation(tmp_path: Path) -> None:
    """行継続は区切りにしない（正常系）。"""
    # 準備
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# b\n", encoding="utf-8")
    command = "cat \\\n  a.md \\\n  b.md"
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "a.md"), str(tmp_path / "b.md")]


def test_extract_read_paths_when_heredoc(tmp_path: Path) -> None:
    """ヒアドキュメントの本文の行は見ない（正常系）。"""
    # 準備
    (tmp_path / "x.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "y.md").write_text("# y\n", encoding="utf-8")
    command = "cat <<'EOF' > out.md\ncat x.md\nEOF\ncat y.md"
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "y.md")]


def test_extract_read_paths_when_escaped_or_inner_quoted(tmp_path: Path) -> None:
    """エスケープした空白・語の途中の引用符・エスケープした引用符のパスを取り出す（正常系）。"""
    # 準備
    (tmp_path / "src" / "my dir").mkdir(parents=True)
    (tmp_path / "dir").mkdir()
    (tmp_path / "a b.md").write_text("# ab\n", encoding="utf-8")
    (tmp_path / "src" / "my dir" / "x.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "dir" / "it's.md").write_text("# it\n", encoding="utf-8")
    command = r'cat a\ b.md src/"my dir"/x.md dir/it\'s.md'
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [
        str(tmp_path / "a b.md"),
        str(tmp_path / "src" / "my dir" / "x.md"),
        str(tmp_path / "dir" / "it's.md"),
    ]


def test_extract_read_paths_when_escaped_glob(tmp_path: Path) -> None:
    """引用符の中と `\\` の直後の glob の文字は文字どおりに扱う（正常系）。"""
    # 準備
    (tmp_path / "[x].md").write_text("# bracket\n", encoding="utf-8")
    (tmp_path / "*.md").write_text("# star\n", encoding="utf-8")
    (tmp_path / "x.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    command = r'cat "[x].md" \*.md'
    # 実行
    result = extract_read_paths(command, tmp_path, READ_COMMANDS)
    # 検証
    assert result == [str(tmp_path / "[x].md"), str(tmp_path / "*.md")]


def test_search_output_base(tmp_path: Path) -> None:
    """検索のコマンドの基準を返す（正常系）。"""
    # 実行
    result = service.search_output_base("find src -type f | head", tmp_path)
    # 検証
    assert result == tmp_path


def test_search_output_base_when_cd(tmp_path: Path) -> None:
    """cd で基準を動かす（正常系）。"""
    # 準備
    (tmp_path / "sub").mkdir()
    # 実行
    result = service.search_output_base("cd sub && grep -rl foo .", tmp_path)
    # 検証
    assert result == tmp_path / "sub"


def test_search_output_base_when_ls_dir(tmp_path: Path) -> None:
    """ls のフォルダを基準にする（正常系）。"""
    # 準備
    (tmp_path / "src").mkdir()
    # 実行
    result = service.search_output_base("ls -1 src", tmp_path)
    # 検証
    assert result == tmp_path / "src"


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("git merge main", id="git"),
        pytest.param("cat a.md", id="cat"),
        pytest.param("rgx foo", id="partial_name"),
    ],
)
def test_search_output_base_when_not_search(tmp_path: Path, command: str) -> None:
    """検索でないコマンドは None を返す（正常系）。"""
    # 実行
    result = service.search_output_base(command, tmp_path)
    # 検証
    assert result is None


def test_search_output_base_when_unparsable(tmp_path: Path) -> None:
    """分けられないコマンドは例外を送出せず None を返す（正常系）。"""
    # 実行
    result = service.search_output_base('grep "foo', tmp_path)
    # 検証
    assert result is None


def test_search_output_base_when_quoted_cd(tmp_path: Path) -> None:
    """引用符で包んだ cd の先を基準にする（正常系）。"""
    # 準備
    (tmp_path / "sub dir").mkdir()
    # 実行
    result = service.search_output_base('cd "sub dir" && grep -rl foo .', tmp_path)
    # 検証
    assert result == tmp_path / "sub dir"


def test_search_output_base_when_escaped_cd(tmp_path: Path) -> None:
    """エスケープした空白を含む cd の先を基準にする（正常系）。"""
    # 準備
    (tmp_path / "my dir").mkdir()
    # 実行
    result = service.search_output_base(r"cd my\ dir && grep -rl foo .", tmp_path)
    # 検証
    assert result == tmp_path / "my dir"


def test_extract_result_paths(tmp_path: Path) -> None:
    """パスだけの行と `{パス}:…` の行を拾う（正常系）。"""
    # 準備
    (tmp_path / "a.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# b\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    lines = ["a.py", "b.md:3:x", "b.md:1", "missing.py", "sub"]
    # 実行
    result = service.extract_result_paths(lines, tmp_path)
    # 検証
    assert result.paths == (str(tmp_path / "a.py"), str(tmp_path / "b.md"))
    assert result.unchecked == 0


def test_extract_result_paths_when_colon_in_name(tmp_path: Path) -> None:
    """名前に `:` を含むファイルを行全体で拾う（正常系）。"""
    # 準備
    (tmp_path / "a:b.md").write_text("# ab\n", encoding="utf-8")
    # 実行
    result = service.extract_result_paths(["a:b.md"], tmp_path)
    # 検証
    assert result.paths == (str(tmp_path / "a:b.md"),)


def test_extract_result_paths_when_over_limit(
    tmp_path: Path,
    make_files: Callable[[int], list[str]],
) -> None:
    """上限を超えた分を件数にする（正常系）。"""
    # 準備
    lines = make_files(105)
    # 実行
    result = service.extract_result_paths(lines, tmp_path, limit=100)
    # 検証
    assert len(result.paths) == 100
    assert result.paths[0] == str(tmp_path / "f000.md")
    assert result.paths[-1] == str(tmp_path / "f099.md")
    assert result.unchecked == 5
