"""単一ユースケース「未読のルールの案内を受ける」の E2E テスト。"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

GUIDANCE_START = "操作の対象に当たる未読のルールがあります"
NON_BLOCKING_GUIDANCE = "必要に応じて下の場所を Read で読んでください"
WRITE_PROMPT = "Write で {target} に「hello」と書いてください。他のことはしないでください。"
RULE_COUNT = 100
GUIDANCE_LIMIT = 10000


def _reason_from_guidance(reason: str) -> str:
    """止めた理由の文面のうち、案内の冒頭から末尾までを返す。"""
    return reason[reason.index(GUIDANCE_START) :]


def test_normal_when_blocked(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
) -> None:
    """未読のルールで Write が止められ、案内にルールの場所が載る（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]
    assert "Read で読んでから" in run.denial_reasons[0]
    assert not target.exists()


def test_normal_when_already_read(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
) -> None:
    """既読のルールでは Write が止められず、対象のファイルが書かれる（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    read_prompt = f"Read で {rule} を読んでください。他のことはしないでください。"
    read_run = run_claude(read_prompt, allow=["Read"])
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_PROMPT.format(target=target),
        allow=["Write", "Edit"],
        resume=read_run.session_id,
    )
    # 検証
    assert run.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_rule_changed_after_read(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
) -> None:
    """読んだ後に本文が変わったルールでは Write が止められ、案内にルールの場所が載る（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    read_prompt = f"Read で {rule} を読んでください。他のことはしないでください。"
    read_run = run_claude(read_prompt, allow=["Read"])
    # 続ける前に、ルールの本文へ 1 行を追加する
    rule.write_text("# ノートの規約\n追記した行\n", encoding="utf-8")
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_PROMPT.format(target=target), allow=["Write"], resume=read_run.session_id
    )
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]
    assert "Read で読んでから" in run.denial_reasons[0]
    assert not target.exists()


def test_normal_when_not_blocked(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
    guided_locations: Callable[[str], list[str]],
    marker: Callable[[str], str],
) -> None:
    """書く操作だけが必須のルールでは、Read を止めずに案内し、案内済みにする（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    file_marker = marker("FILE-BODY")
    target = e2e_project / "notes.txt"
    target.write_text(f"{file_marker}\n", encoding="utf-8")
    prompt = f"Read で {target} を読み、中身をそのまま答えてください。他のことはしないでください。"
    # 実行
    run = run_claude(prompt, allow=["Read"])
    # 検証
    assert run.denied_tools == []
    assert file_marker in run.answer
    transcript = transcript_text(run.session_id)
    assert NON_BLOCKING_GUIDANCE in transcript
    assert str(rule) in transcript
    assert guided_locations(run.session_id) == [str(rule)]


def test_normal_when_read_by_bash(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
) -> None:
    """読む操作が必須のルールで、Bash の cat が止められる（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["read"]}))
    target = e2e_project / "notes.txt"
    target.write_text("notes\n", encoding="utf-8")
    prompt = f"Bash の cat で {target} を読んでください。他のことはしないでください。"
    # 実行
    run = run_claude(prompt, allow=["Bash"], deny=["Read"])
    # 検証
    assert "Bash" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]


@pytest.fixture
def hundred_rules(
    tmp_path: Path, make_rule: Callable[..., Path], make_index: Callable[..., Path]
) -> Path:
    """場所が 150 字前後のルールを 100 件置き、全て書く操作を必須にした索引を返す。"""
    long_dir = "d" * 120
    rules = [
        make_rule(f"{long_dir}/{number:03d}.md", f"# 規約 {number}\n")
        for number in range(RULE_COUNT)
    ]
    return make_index(
        *({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]} for rule in rules)
    )


def test_normal_when_guidance_too_long(
    e2e_project: Path,
    hundred_rules: Path,
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
) -> None:
    """案内が長いとき、10,000 字以内に収めて載せきれなかった件数を添える（正常シナリオ）。"""
    # 準備
    configure_index(hundred_rules)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    guidance = _reason_from_guidance(run.denial_reasons[0])
    assert "Write" in run.denied_tools
    assert len(guidance) <= GUIDANCE_LIMIT
    assert re.search(r"ほか \d+ 件のルール", guidance)


def test_error_when_index_unreadable(
    tmp_path: Path,
    e2e_project: Path,
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """索引が読めないとき、Write を止めずに、読めなかった索引の場所と理由が載る（異常シナリオ）。"""
    # 準備
    broken = tmp_path / "broken.yaml"
    broken.write_text("rules:\n  - foo: bar\n", encoding="utf-8")
    configure_index(broken)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write", "Edit"])
    # 検証
    assert run.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")
    transcript = transcript_text(run.session_id)
    assert str(broken) in transcript
    assert "許さないキー" in transcript


def test_error_when_settings_unreadable(
    tmp_path: Path,
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_env: Callable[..., None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """設定ファイルが読めないとき、Write を止めずに、読めなかった設定ファイルの場所と理由が載る（異常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}, to="project/rules.yaml")
    broken = tmp_path / "broken_settings.yaml"
    broken.write_text("unknown: value\n", encoding="utf-8")
    configure_env({"RULE_INJECT_CONFIG": str(broken)})
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write", "Edit"])
    # 検証
    assert run.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")
    transcript = transcript_text(run.session_id)
    assert str(broken) in transcript
    assert "許さないキー" in transcript


def test_normal_when_already_guided(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
    guidance_count: Callable[[str, str], int],
    marker: Callable[[str], str],
) -> None:
    """案内済みのルールでは、同じファイルをもう一度 Read しても案内されない（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    file_marker = marker("FILE-BODY")
    target = e2e_project / "notes.txt"
    target.write_text(f"{file_marker}\n", encoding="utf-8")
    prompt = f"Read で {target} を読み、中身をそのまま答えてください。他のことはしないでください。"
    first_run = run_claude(prompt, allow=["Read"])
    guided_count = guidance_count(first_run.session_id, NON_BLOCKING_GUIDANCE)
    # 実行
    run = run_claude(prompt, allow=["Read"], resume=first_run.session_id)
    # 検証
    assert guided_count == 1
    assert run.denied_tools == []
    assert file_marker in run.answer
    assert guidance_count(run.session_id, NON_BLOCKING_GUIDANCE) == guided_count


def test_normal_when_default_index(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_env: Callable[..., None],
    run_claude: Callable[..., Any],
) -> None:
    """設定ファイルが無いとき、プロジェクトの直下の `rules.yaml` で Write が止められる（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}, to="project/rules.yaml")
    configure_env()
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]
    assert "索引を読めませんでした" not in run.denial_reasons[0]


def test_normal_when_rule_has_variable(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
) -> None:
    """`rule` の変数参照を展開した場所で Write が止められる（正常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    index = make_index(
        {"rule": '"!{E2E_RULES_DIR}/notes.md"', "paths": ["**/*.txt"], "on": ["write"]}
    )
    configure_index(index, extra_env={"E2E_RULES_DIR": str(rule.parent)})
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write"])
    # 検証
    assert "Write" in run.denied_tools
    assert str(rule) in run.denial_reasons[0]
    assert "!{E2E_RULES_DIR}" not in run.denial_reasons[0]


def test_error_when_rule_variable_unset(
    e2e_project: Path,
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """未設定の変数参照を持つエントリを読み飛ばし、Write を止めずに理由が載る（異常シナリオ）。"""
    # 準備
    index = make_index(
        {"rule": '"!{E2E_UNSET_RULES_DIR}/notes.md"', "paths": ["**/*.txt"], "on": ["write"]}
    )
    configure_index(index)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write", "Edit"])
    # 検証
    assert run.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")
    transcript = transcript_text(run.session_id)
    assert str(index) in transcript
    assert "E2E_UNSET_RULES_DIR" in transcript


def test_error_when_regex_unreadable(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
    transcript_text: Callable[[str], str],
) -> None:
    """読めない正規表現を持つエントリを読み飛ばし、Write を止めずに理由が載る（異常シナリオ）。"""
    # 準備
    rule = make_rule("notes.md", "# ノートの規約\n")
    index = make_index({"rule": str(rule), "paths": ["re:["], "on": ["write"]})
    configure_index(index)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(WRITE_PROMPT.format(target=target), allow=["Write", "Edit"])
    # 検証
    assert run.denied_tools == []
    assert "hello" in target.read_text(encoding="utf-8")
    transcript = transcript_text(run.session_id)
    assert str(index) in transcript
    assert "re:[" in transcript
    assert "unterminated character set" in transcript
