"""ルール案内（PreToolUse フック）の結合テスト。"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

RULE = "/r/python.md"
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
def write_payload(
    tmp_path: Path, hook_payload: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """まだ無い .py のパスを Write する PreToolUse の入力を作る factory。"""

    def _make(relative: str = "src/app.py") -> dict[str, Any]:
        """tmp_path の下の relative を書く Write の入力を返す。"""
        return hook_payload(
            "PreToolUse",
            tool_name="Write",
            tool_input={"file_path": str(tmp_path / relative), "content": ""},
        )

    return _make


def test_normal_when_blocked(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """書く操作が必須の未読のルールで Write を止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert "Read で読んでから" in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_normal_when_already_read(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    write_record: Callable[..., Path],
) -> None:
    """当たるルールが既読なら何も出さない（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = write_index({"rule": str(rule), "paths": ["**/*.py"], "on": ["write"]})
    write_record([f"{rule}\t{HASH_RULE}"])
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_not_blocked(
    tmp_path: Path,
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """操作の種別が `on` に当たらない未読のルールは止めずに案内し、案内済みにする（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    payload = hook_payload(
        "PreToolUse",
        tool_name="Read",
        tool_input={"file_path": str(tmp_path / "src" / "app.py")},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]
    assert "やり直してください" not in output["additionalContext"]
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [RULE]
    assert completed.returncode == 0


def test_normal_when_read_by_bash(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """読むコマンドの引数から取り出したパスで照合して止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["read"]})
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print()\n", encoding="utf-8")
    payload = hook_payload(
        "PreToolUse",
        tool_name="Bash",
        tool_input={"command": "cd src && cat app.py | head -n 5"},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


def test_normal_when_mcp_tool(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """`tools` の glob に当たる MCP のツールの呼び出しを止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "tools": ["mcp__*__create_*"]})
    payload = hook_payload("PreToolUse", tool_name="mcp__github__create_issue", tool_input={})
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


def test_normal_when_duplicate_entries(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    rule_file: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """同じルールのエントリ 2 つを 1 件にまとめ、どちらかが止めるなら止める（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = make_index(
        index_text(
            {"rule": str(rule), "paths": ["**/*.py"], "on": ["read"]},
            {"rule": "./rules/python.md", "paths": ["**/*.py"], "on": ["write"]},
        )
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"].count(str(rule)) == 1


def test_normal_when_excluded(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`exclude` に当たるパスには案内しない（正常系）。"""
    # 準備
    index = write_index(
        {"rule": RULE, "paths": ["**/*.py"], "exclude": ["**/tests/**"], "on": ["write"]}
    )
    # 実行
    completed = run_hook("rule_guide", write_payload("tests/test_app.py"), index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


@pytest.fixture
def hundred_entries() -> list[dict[str, Any]]:
    """1 件 150 字前後の場所を持つ 100 件のエントリ（半数は書く操作が必須、半数は読む操作が必須）。"""
    return [
        {
            "rule": f"/rules/{'write' if number % 2 == 0 else 'read'}/{number:03d}/" + "x" * 130,
            "paths": ["**/*.py"],
            "on": ["write"] if number % 2 == 0 else ["read"],
        }
        for number in range(100)
    ]


def test_normal_when_guidance_too_long(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    hundred_entries: list[dict[str, Any]],
) -> None:
    """案内が 10,000 字を超えるとき、収まる分だけ載せて残りの件数を添える（正常系）。"""
    # 準備
    index = write_index(*hundred_entries)
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    reason = json.loads(completed.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert len(reason) <= 10000
    assert reason.index("/rules/write/") < reason.index("/rules/read/")
    assert re.search(r"ほか \d+ 件のルール", reason)


def test_error_when_index_unreadable(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """索引が無いか書式に合わないとき、操作を止めずに理由を載せる（異常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    broken = make_index("rules:\n  - foo: bar\n", "broken.yaml")
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=[missing, broken])
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(missing) in output["additionalContext"]
    assert str(broken) in output["additionalContext"]
    assert completed.returncode == 0


def test_error_when_record_unreadable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    write_record: Callable[..., Path],
    unwritable: Callable[[Path, int], Path],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """記録ファイルが読めないとき、操作を止めずに理由を載せ、ログに書く（異常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    record_file = unwritable(write_record([RULE]), 0o000)
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(record_file) in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_record"
    assert completed.returncode == 0


def test_normal_when_read_by_grep(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """組み込みの Grep が指すファイルで照合して止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["read"]})
    target = tmp_path / "app.py"
    target.write_text("print()\n", encoding="utf-8")
    payload = hook_payload(
        "PreToolUse", tool_name="Grep", tool_input={"pattern": "print", "path": str(target)}
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]


@pytest.fixture
def read_payload(
    tmp_path: Path, hook_payload: Callable[..., dict[str, Any]]
) -> Callable[..., dict[str, Any]]:
    """まだ無い .py のパスを Read する PreToolUse の入力を作る factory。"""

    def _make(relative: str = "src/app.py") -> dict[str, Any]:
        """tmp_path の下の relative を読む Read の入力を返す。"""
        return hook_payload(
            "PreToolUse",
            tool_name="Read",
            tool_input={"file_path": str(tmp_path / relative)},
        )

    return _make


def test_normal_when_already_guided(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    read_payload: Callable[..., dict[str, Any]],
    write_guided: Callable[..., Path],
    read_lines: Callable[[Path], list[str]],
) -> None:
    """案内済みのルールは止めない案内を出さない（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    write_guided([RULE])
    # 実行
    completed = run_hook("rule_guide", read_payload(), index=index)
    # 検証
    assert completed.stdout == ""
    assert read_lines(state_dir / f"{session_id}.guided.txt") == [RULE]
    assert completed.returncode == 0


def test_normal_when_blocked_twice(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """止める案内に並べたルールは案内済みにせず、次も止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    # 実行
    first = run_hook("rule_guide", write_payload(), index=index)
    second = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    assert json.loads(first.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert json.loads(second.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not (state_dir / f"{session_id}.guided.txt").exists()


def test_normal_when_default_index(
    default_log_folder: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """設定ファイルが無いとき、既定の置き場所の索引で案内する（正常系）。"""
    # 準備
    make_index(
        index_text({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]}),
        "rules.yaml",
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), no_config=True)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert "索引を読めませんでした" not in output["permissionDecisionReason"]
    assert not default_log_folder.exists()


def test_normal_when_indexes_empty(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    settings_text: Callable[..., str],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """当たった `projects` の要素の `indexes` が空の並びのとき、プロジェクトの既定の置き場所の索引を読まない（正常系）。"""
    # 準備
    make_index(
        index_text({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]}),
        "rules.yaml",
    )
    config_text = settings_text() + f"projects:\n  - match: {tmp_path.name}\n    indexes: []\n"
    # 実行
    completed = run_hook("rule_guide", write_payload(), config_text=config_text)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_projects_matched(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    settings_text: Callable[..., str],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`match` が当たった `projects` の要素の索引だけを、並びの順に足して案内する（正常系）。"""
    # 準備
    entry = {"paths": ["**/*.py"], "on": ["write"]}
    make_index(index_text({"rule": "/r/a.md", **entry}), "rules/a.yaml")
    index_b = make_index(index_text({"rule": "/r/b.md", **entry}), "b.yaml")
    index_c = make_index(index_text({"rule": "/r/c.md", **entry}), "c.yaml")
    config_text = settings_text(indexes=[]) + (
        "projects:\n"
        f"  - match: {tmp_path.name}\n"
        "    indexes: [rules/a.yaml]\n"
        f"  - match: {tmp_path}\n"
        f'    indexes: ["{index_b}"]\n'
        "  - match: other-project\n"
        f'    indexes: ["{index_c}"]\n'
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), config_text=config_text)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "/r/a.md" in output["permissionDecisionReason"]
    assert "/r/b.md" in output["permissionDecisionReason"]
    assert "/r/c.md" not in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_normal_when_worktree_matched(
    tmp_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    settings_text: Callable[..., str],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`.claude/worktrees/` の下で起動したとき、本体のフォルダ名で `projects` の要素を当てる（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    worktree = tmp_path / "repo" / ".claude" / "worktrees" / "feature"
    worktree.mkdir(parents=True)
    config_text = settings_text(indexes=[]) + (
        f'projects:\n  - match: repo\n    indexes: ["{index}"]\n'
    )
    # 実行
    completed = run_hook(
        "rule_guide", write_payload(), config_text=config_text, project_dir=worktree
    )
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_error_when_settings_unreadable(
    config_path: Path,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    make_index: Callable[..., Path],
    index_text: Callable[..., str],
    write_payload: Callable[..., dict[str, Any]],
    read_default_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """設定ファイルが知らないキーを持つとき、既定値で動かさず、操作を止めずに理由を載せる（異常系）。"""
    # 準備
    make_index(
        index_text({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]}),
        "rules.yaml",
    )
    config_text = "projects:\n  - match: repo\n    index:\n      - /a.yaml\n"
    # 実行
    completed = run_hook("rule_guide", write_payload(), config_text=config_text)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(config_path) in output["additionalContext"]
    assert "index" in output["additionalContext"]
    assert RULE not in output["additionalContext"]
    logged = read_default_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_settings"
    assert completed.returncode == 0


def test_normal_when_rule_has_variable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`rule` の変数参照を環境変数で展開した場所で案内する（正常系）。"""
    # 準備
    index = write_index({"rule": '"!{RULES_DIR}/python.md"', "paths": ["**/*.py"], "on": ["write"]})
    # 実行
    completed = run_hook(
        "rule_guide", write_payload(), index=index, extra_env={"RULES_DIR": "/rules-dir"}
    )
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "/rules-dir/python.md" in output["permissionDecisionReason"]
    assert "!{RULES_DIR}" not in output["permissionDecisionReason"]


def test_error_when_rule_variable_unset(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """未設定の名前が残ったエントリを読み飛ばし、止めずに理由を載せる（異常系）。"""
    # 準備
    index = write_index(
        {"rule": '"!{UNSET_DIR}/python.md"', "paths": ["**/*.py"], "on": ["write"]},
        {"rule": RULE, "paths": ["**/*.py"], "on": ["read"]},
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(index) in output["additionalContext"]
    assert "!{UNSET_DIR}/python.md" in output["additionalContext"]
    assert "UNSET_DIR" in output["additionalContext"]
    assert RULE in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_index"
    assert completed.returncode == 0


def test_error_when_guided_record_unwritable(
    state_dir: Path,
    session_id: str,
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    read_payload: Callable[..., dict[str, Any]],
    unwritable: Callable[[Path, int], Path],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """案内済みの記録に書けないとき、案内を出したうえで理由を載せ、ログに書く（異常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": ["**/*.py"], "on": ["write"]})
    state_dir.mkdir()
    unwritable(state_dir, 0o500)
    # 実行
    completed = run_hook("rule_guide", read_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert RULE in output["additionalContext"]
    assert str(state_dir / f"{session_id}.guided.txt") in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "write_record"
    assert completed.returncode == 0


MCP_SEARCH_ENTRY = {
    "rule": RULE,
    "tools": ["mcp__*__search_*"],
    "args": {"tags": ["re:^python$"], "filter.kind": ["rule"]},
}


def test_normal_when_mcp_args_match(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """`args` のパターンに引数の値が当たる MCP のツールの呼び出しを止める（正常系）。"""
    # 準備
    index = write_index(MCP_SEARCH_ENTRY)
    payload = hook_payload(
        "PreToolUse",
        tool_name="mcp__docs__search_docs",
        tool_input={"query": "x", "tags": ["go", "python"], "filter": {"kind": "rule"}},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_normal_when_mcp_args_unmatched(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    hook_payload: Callable[..., dict[str, Any]],
) -> None:
    """ツール名に当たっても、`args` のキーが無いか値が当たらなければ案内しない（正常系）。"""
    # 準備
    index = write_index(MCP_SEARCH_ENTRY)
    payload = hook_payload(
        "PreToolUse",
        tool_name="mcp__docs__search_docs",
        tool_input={"query": "x", "tags": ["go"]},
    )
    # 実行
    completed = run_hook("rule_guide", payload, index=index)
    # 検証
    assert completed.stdout == ""
    assert completed.returncode == 0


def test_normal_when_regex_path(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
) -> None:
    """`re:` で始まる `paths` のパターンに部分一致するパスの Write を止める（正常系）。"""
    # 準備
    index = write_index({"rule": RULE, "paths": [r"re:/src/[a-z_]+\\.py$"], "on": ["write"]})
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert RULE in output["permissionDecisionReason"]
    assert completed.returncode == 0


def test_error_when_regex_unreadable(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """コンパイルできない正規表現を持つエントリを読み飛ばし、止めずに理由を載せる（異常系）。"""
    # 準備
    broken_rule = "/r/broken.md"
    index = write_index(
        {"rule": broken_rule, "paths": ["re:["], "on": ["write"]},
        {"rule": RULE, "paths": ["**/*.py"], "on": ["read"]},
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(index) in output["additionalContext"]
    assert "re:[" in output["additionalContext"]
    assert "unterminated character set" in output["additionalContext"]
    assert RULE in output["additionalContext"]
    assert broken_rule not in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_index"
    assert completed.returncode == 0


def test_error_when_rule_is_url(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    read_log: Callable[[], list[dict[str, Any]]],
) -> None:
    """`rule` が URL のエントリを読み飛ばし、止めずに理由を載せる（異常系）。"""
    # 準備
    url_rule = "https://example.com/python.md"
    index = write_index(
        {"rule": url_rule, "paths": ["**/*.py"], "on": ["write"]},
        {"rule": RULE, "paths": ["**/*.py"], "on": ["read"]},
    )
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in output
    assert str(index) in output["additionalContext"]
    assert url_rule in output["additionalContext"]
    assert "Read で読めない" in output["additionalContext"]
    assert RULE in output["additionalContext"]
    logged = read_log()
    assert len(logged) == 1
    assert logged[0]["operation"] == "read_index"
    assert completed.returncode == 0


def test_normal_when_rule_changed_after_read(
    run_hook: Callable[..., subprocess.CompletedProcess[str]],
    write_index: Callable[..., Path],
    write_payload: Callable[..., dict[str, Any]],
    rule_file: Callable[..., Path],
    write_record: Callable[..., Path],
) -> None:
    """読んだ後に変わったルールを未読として止めて案内する（正常系）。"""
    # 準備
    rule = rule_file("python.md")
    index = write_index({"rule": str(rule), "paths": ["**/*.py"], "on": ["write"]})
    write_record([f"{rule}\t{HASH_RULE}"])
    # 記録を作った後に、ルールのファイルへ 1 行を追記する
    rule.write_text("# 規約\n追記\n", encoding="utf-8")
    # 実行
    completed = run_hook("rule_guide", write_payload(), index=index)
    # 検証
    output = json.loads(completed.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert str(rule) in output["permissionDecisionReason"]
    assert completed.returncode == 0
