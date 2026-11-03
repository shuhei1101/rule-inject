"""複合ユースケース「ルールを読んでからファイルを触る」の E2E テスト。"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

WRITE_THEN_READ_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、案内に従って Read でルールの本文を読み、"
    "同じ書き込みをやり直してください。"
)
WRITE_THEN_SEARCH_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、案内に従って、ルールの本文を Read ではなく MCP のツール search_docs で読み、"
    "同じ書き込みをやり直してください。"
)
SEARCH_TOOL = "mcp__docs__search_docs"
WRITE_PROMPT = "Write で {target} に「hello」と書いてください。止められたら、案内に従ってから同じ書き込みをやり直してください。"
SECTIONED_BODY = "# ノートの規約\n\n## 命名\n\n小文字で書く\n\n## 例外\n\n握りつぶさない\n"
NAMING_SECTION = "## 命名\n\n小文字で書く\n"
WRITE_THEN_CAT_PROMPT = (
    "Write で {target} に「hello」と書いてください。"
    "止められたら、案内に従って、ルールの本文を Read ではなく Bash の cat で読み、"
    "同じ書き込みをやり直してください。"
)


@pytest.fixture
def rule_and_body(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    marker: Callable[[str], str],
) -> tuple[Path, str]:
    """書く操作を必須とするルールと索引を置き、ルールのパスと本文の目印を返す。"""
    body_marker = marker("RULE-BODY")
    rule = make_rule("notes.md", f"# ノートの規約\n{body_marker}\n")
    configure_index(make_index({"rule": str(rule), "paths": ["**/*.txt"], "on": ["write"]}))
    return rule, body_marker


def test_normal(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """止められた書く操作が、本文を読んだ後のやり直しで通る（正常シナリオ）。"""
    # 準備
    rule, body_marker = rule_and_body
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=target),
        allow=["Write", "Edit", "Read"],
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "Read で参照してください" in run.denial_reasons[0]
    assert body_marker in "\n".join(run.tool_results.values())
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_read_by_bash(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """本文を Bash の cat で読んでも、やり直した書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, _ = rule_and_body
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_CAT_PROMPT.format(target=target),
        allow=["Write", "Edit", "Bash"],
        deny=["Read"],
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_after_compact(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
) -> None:
    """圧縮の後は、また止められ、本文を取得し直すと書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, _ = rule_and_body
    first_target = e2e_project / "first.txt"
    first_run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=first_target),
        allow=["Write", "Edit", "Read"],
        max_turns=8,
    )
    run_claude("/compact", resume=first_run.session_id, max_turns=None)
    second_target = e2e_project / "second.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=second_target),
        allow=["Write", "Edit", "Read"],
        resume=first_run.session_id,
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert "hello" in second_target.read_text(encoding="utf-8")


def test_normal_when_read_by_mcp_result(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    docs_mcp_config: Callable[[str], Path],
    run_claude: Callable[..., Any],
) -> None:
    """本文を文書の MCP のツールの結果で読むと、やり直した書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, body_marker = rule_and_body
    result = f'<document path="{rule}" scope="full">\n{rule.read_text(encoding="utf-8")}</document>'
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_SEARCH_PROMPT.format(target=target),
        allow=["Write", "Edit", SEARCH_TOOL],
        deny=["Read", "Bash"],
        mcp_config=docs_mcp_config(result),
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert body_marker in "\n".join(run.tool_results.values())
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_rule_changed(
    e2e_project: Path,
    rule_and_body: tuple[Path, str],
    run_claude: Callable[..., Any],
    marker: Callable[[str], str],
) -> None:
    """ルールが変わった後は、また止められ、本文を読み直すと書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, _ = rule_and_body
    first_target = e2e_project / "first.txt"
    first_run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=first_target),
        allow=["Write", "Edit", "Read"],
        max_turns=8,
    )
    # 続ける前に、読み直したことを応答で見分けられる 1 行をルールの本文へ追加する
    changed_marker = marker("RULE-CHANGED")
    rule.write_text(rule.read_text(encoding="utf-8") + f"{changed_marker}\n", encoding="utf-8")
    second_target = e2e_project / "second.txt"
    # 実行
    run = run_claude(
        WRITE_THEN_READ_PROMPT.format(target=second_target),
        allow=["Write", "Edit", "Read"],
        resume=first_run.session_id,
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    assert str(rule) in run.denial_reasons[0]
    assert changed_marker in "\n".join(run.tool_results.values())
    assert "hello" in second_target.read_text(encoding="utf-8")


@pytest.fixture
def guided_rule(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    marker: Callable[[str], str],
) -> tuple[Path, str]:
    """書く操作を必須とし、参照するツールと `sections` を含む引数を記載したルールを置き、ルールのパスと引数の id を返す。"""
    rule = make_rule("notes.md", SECTIONED_BODY)
    id_marker = marker("RULE-ID")
    arguments = json.dumps(
        {"filter": {"field": "id", "op": "eq", "values": [id_marker]}, "sections": ["命名"]},
        ensure_ascii=False,
    )
    configure_index(
        make_index(
            {
                "rule": str(rule),
                "paths": ["**/*.txt"],
                "on": ["write"],
                "read_tool": {"tool": SEARCH_TOOL, "args": arguments},
            }
        )
    )
    return rule, id_marker


def test_normal_when_read_by_guided_tool(
    e2e_project: Path,
    guided_rule: tuple[Path, str],
    section_docs_mcp_config: Callable[[Path, str], tuple[Path, Path]],
    run_claude: Callable[..., Any],
) -> None:
    """止められた書く操作が、案内されたツールと引数でセクションだけを読んだ後のやり直しで通る（正常シナリオ）。"""
    # 準備
    rule, id_marker = guided_rule
    mcp_config, calls = section_docs_mcp_config(rule, NAMING_SECTION)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_PROMPT.format(target=target),
        allow=["Write", "Edit", SEARCH_TOOL, "Read"],
        mcp_config=mcp_config,
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    lines = run.denial_reasons[0].splitlines()
    assert id_marker in lines[lines.index(f"- {rule}") + 1]
    received = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    assert {"field": "id", "op": "eq", "values": [id_marker]} in [
        call.get("filter") for call in received
    ]
    assert ["命名"] in [call.get("sections") for call in received]
    assert "hello" in target.read_text(encoding="utf-8")


def test_normal_when_guided_tool_unavailable(
    e2e_project: Path,
    guided_rule: tuple[Path, str],
    section_docs_mcp_config: Callable[[Path, str], tuple[Path, Path]],
    run_claude: Callable[..., Any],
) -> None:
    """案内されたツールが使えないときは、パスを Read で読んだ後のやり直しで書く操作が通る（正常シナリオ）。"""
    # 準備
    rule, id_marker = guided_rule
    mcp_config, _ = section_docs_mcp_config(rule, NAMING_SECTION)
    target = e2e_project / "notes.txt"
    # 実行
    run = run_claude(
        WRITE_PROMPT.format(target=target),
        allow=["Write", "Edit", "Read"],
        deny=[SEARCH_TOOL],
        mcp_config=mcp_config,
        max_turns=8,
    )
    # 検証
    assert run.denied_tools[0] == "Write"
    lines = run.denial_reasons[0].splitlines()
    assert id_marker in lines[lines.index(f"- {rule}") + 1]
    assert "## 例外" in "\n".join(run.tool_results.values())
    assert "hello" in target.read_text(encoding="utf-8")
