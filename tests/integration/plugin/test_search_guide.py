"""検索結果の案内（PostToolUse フック）の結合テスト。"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

RULE = "/r/python.md"
OTHER_RULE = "/r/markdown.md"
# 本文が `# 規約\n` のルールの本文のハッシュ
HASH_RULE = "sha256:2bd9e5f1266128992c621bc85f433d4ab35c1307ec01c91c7e1efef9068d0fa8"


@pytest.fixture
def write_index(
    make_index: Callable[..., Path], index_text: Callable[..., str]
) -> Callable[..., Path]:
    """エントリを並べた索引を書き、そのパスを返す factory。"""

    def _write(*entries: dict[str, Any]) -> Path:
        """entries を索引の YAML にして書く。"""
        return make_index(index_text(*entries))

    return _write


@pytest.fixture
def two_rule_index(write_index: Callable[..., Path]) -> Path:
    """`.py` と `.md` に当たる、別のルールを指すエントリを 1 つずつ持つ索引。"""
    return write_index(
        {"rule": RULE, "paths": ["**/*.py"], "on": ["write"]},
        {"rule": OTHER_RULE, "paths": ["**/*.md"], "on": ["write"]},
    )


@pytest.fixture
def src_files(tmp_path: Path) -> Path:
    """`src/app.py` と `src/doc.md` を置き、`src` のパスを返す。"""
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "app.py").write_text("print()\n", encoding="utf-8")
    (folder / "doc.md").write_text("# doc\n", encoding="utf-8")
    return folder


@pytest.fixture
def search_payload(hook_payload: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """検索ツールの結果を持つ PostToolUse の入力を作る factory。"""

    def _make(
        tool_name: str, response: dict[str, Any], command: str | None = None
    ) -> dict[str, Any]:
        """tool_name・結果・Bash のコマンドから入力を組み立てる。"""
        tool_input = {"command": command} if command else {"pattern": "needle", "path": "src"}
        return hook_payload(
            "PostToolUse", tool_name=tool_name, tool_input=tool_input, tool_response=response
        )

    return _make


@pytest.fixture
def many_filenames(tmp_path: Path) -> list[str]:
    """実在する 105 件のファイル名（先頭に `.md` を 1 件、続けて `.txt` を 99 件、その後に `.py` を 1 件と `.txt` を 4 件）を置いて並べる。"""
    names = (
        ["a.md"]
        + [f"t{number:03d}.txt" for number in range(99)]
        + ["z.py"]
        + [f"u{number:03d}.txt" for number in range(4)]
    )
    for name in names:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    return names


def test_normal(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """Grep のファイル名の結果に当たる未読のルールを案内し、案内済みにする（正常系）。"""
    # 準備
    payload = search_payload("Grep", {"mode": "files_with_matches", "filenames": ["src/app.py"]})
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PostToolUse"
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]
    assert "読むかは任意" in output["additionalContext"]
    assert "やり直してください" not in output["additionalContext"]
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [RULE]
    assert completed.returncode == 0


def test_normal_when_grep_content(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """Grep の `content` の各行の最初の `:` より前から拾ったパスで案内する（正常系）。"""
    # 準備
    payload = search_payload(
        "Grep", {"mode": "content", "filenames": [], "content": "src/app.py:1:needle"}
    )
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert RULE in output["additionalContext"]


def test_normal_when_glob(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """Glob の `filenames` から拾ったパスで案内する（正常系）。"""
    # 準備
    payload = search_payload("Glob", {"filenames": ["src/app.py"], "numFiles": 1})
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert RULE in output["additionalContext"]


def test_normal_when_bash_search(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """`find` と `grep -n` の標準出力から拾ったパスで案内する（正常系）。"""
    # 準備
    payload = search_payload(
        "Bash",
        {"stdout": "src/app.py\nsrc/doc.md:3:needle\n", "stderr": ""},
        command="find src -type f | head",
    )
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert RULE in output["additionalContext"]
    assert OTHER_RULE in output["additionalContext"]


def test_normal_when_ls(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """`ls {フォルダ}` の出力の名前を、そのフォルダから解いて案内する（正常系）。"""
    # 準備
    payload = search_payload("Bash", {"stdout": "app.py\n", "stderr": ""}, command="ls src")
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert RULE in output["additionalContext"]


def test_normal_when_not_search(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """検索のコマンドでない Bash は、出力に実在するファイルがあっても案内しない（正常系）。"""
    # 準備
    payload = search_payload(
        "Bash",
        {"stdout": f"{src_files / 'app.py'}\n", "stderr": ""},
        command="git merge main",
    )
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_read_or_guided(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    write_guided: Callable[..., Path],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """既読のルールと案内済みのルールは案内しない（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = write_index(
        {"rule": str(rule), "paths": ["**/*.py"], "on": ["write"]},
        {"rule": OTHER_RULE, "paths": ["**/*.md"], "on": ["write"]},
    )
    write_record([f"{rule}\t{HASH_RULE}"])
    write_guided([OTHER_RULE])
    payload = search_payload("Glob", {"filenames": ["src/app.py", "src/doc.md"], "numFiles": 2})
    # 実行
    completed = run_hook("search_guide", payload, index=index)
    # 検証
    assert completed.stdout == ""
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [OTHER_RULE]
    assert completed.returncode == 0


def test_normal_when_too_many_paths(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    many_filenames: list[str],
    search_payload: Callable[..., dict[str, Any]],
) -> None:
    """100 件を超える結果は先頭 100 件だけを照合し、照合しなかった件数を添える（正常系）。"""
    # 準備
    payload = search_payload("Glob", {"filenames": many_filenames, "numFiles": 105})
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert OTHER_RULE in context
    assert RULE not in context
    assert re.search(r"5 件は照合していません", context)
    assert completed.returncode == 0


def test_error_when_index_unreadable(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    make_index: Callable[..., Path],
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """索引が読めないとき、読めた索引で案内を続け、理由を載せる（異常系）。"""
    # 準備
    broken = make_index("rules:\n  - foo: bar\n", "broken.yaml")
    payload = search_payload("Grep", {"mode": "files_with_matches", "filenames": ["src/app.py"]})
    # 実行
    completed = run_hook("search_guide", payload, index=[two_rule_index, broken])
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert RULE in context
    assert str(broken) in context
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_index"
    assert completed.returncode == 0


def test_error_when_guided_record_unwritable(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    two_rule_index: Path,
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    unwritable: Callable[[Path, int], Path],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """案内済みの記録に書けないとき、案内を出したうえで理由を載せ、ログに書く（異常系）。"""
    # 準備
    state_dir.mkdir()
    unwritable(state_dir, 0o500)
    payload = search_payload("Grep", {"mode": "files_with_matches", "filenames": ["src/app.py"]})
    # 実行
    completed = run_hook("search_guide", payload, index=two_rule_index)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert RULE in context
    assert str(state_dir / f"{session_id}.guided.txt") in context
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "write_record"
    assert completed.returncode == 0


def test_normal_when_rule_changed_after_read(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    rule_file: Callable[..., Path],
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """読んだ後に変わったルールを未読として案内する（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = write_index({"rule": str(rule), "paths": ["**/*.py"], "on": ["write"]})
    write_record([f"{rule}\t{HASH_RULE}"])
    # 記録を作った後に、ルールのファイルへ 1 行を追記する
    rule.write_text("# 規約\n追記\n", encoding="utf-8")
    payload = search_payload("Glob", {"filenames": ["src/app.py"], "numFiles": 1})
    # 実行
    completed = run_hook("search_guide", payload, index=index)
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert str(rule) in context
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [str(rule)]
    assert completed.returncode == 0


def test_error_when_settings_unreadable(
    config_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    src_files: Path,
    search_payload: Callable[..., dict[str, Any]],
    settings_text: Callable[..., str],
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが読めないとき、案内せずに理由を載せる（異常系）。"""
    # 準備
    make_index(index_text({"rule": RULE, "paths": ["**/*.py"]}), "rules.yaml")
    payload = search_payload("Grep", {"mode": "files_with_matches", "filenames": ["src/app.py"]})
    # 実行
    completed = run_hook("search_guide", payload, config_text=settings_text(log_retention_days=0))
    # 検証
    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert str(config_path) in context
    assert "global.log_retention_days" in context
    assert RULE not in context
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
    assert completed.returncode == 0
