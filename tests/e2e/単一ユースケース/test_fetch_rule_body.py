"""単一ユースケース「ルールの本文を取得する」の E2E テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

READ_RULES_TOOL = "mcp__plugin_rule-inject_rule-inject__read_rules"


def _tool_results(run: Any) -> str:
    """ツールの結果の文面を、全部つないで返す。"""
    return "\n".join(run.tool_results.values())


def test_normal(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    marker: Callable[[str], str],
) -> None:
    """ルールの場所を渡して、本文を受け取り、既読になる（正常シナリオ）。"""
    # 準備
    body_marker = marker("RULE-BODY")
    rule = make_rule("python.md", f"# Python の規約\n{body_marker}\n")
    configure_index(make_index({"rule": str(rule)}))
    prompt = (
        f"MCP のツール read_rules を 1 回だけ呼んでください。locations に {rule} を渡し、"
        "session_id は渡さないでください。"
    )
    # 実行
    run = run_claude(prompt, allow=[READ_RULES_TOOL])
    # 検証
    assert body_marker in _tool_results(run)
    assert record_locations(run.session_id) == [str(rule)]


def test_normal_when_by_target_path(
    e2e_project: Path,
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    marker: Callable[[str], str],
) -> None:
    """対象のパスを渡して、当たるルールの本文だけを受け取る（正常シナリオ）。"""
    # 準備
    py_marker = marker("PY-RULE")
    ts_marker = marker("TS-RULE")
    py_rule = make_rule("python.md", f"# Python の規約\n{py_marker}\n")
    ts_rule = make_rule("typescript.md", f"# TypeScript の規約\n{ts_marker}\n")
    configure_index(
        make_index(
            {"rule": str(py_rule), "paths": ["**/*.py"]},
            {"rule": str(ts_rule), "paths": ["**/*.ts"]},
        )
    )
    target = e2e_project / "src" / "app.py"
    prompt = (
        f"MCP のツール read_rules を 1 回だけ呼んでください。paths に {target} を渡し、"
        "session_id は渡さないでください。"
    )
    # 実行
    run = run_claude(prompt, allow=[READ_RULES_TOOL])
    # 検証
    results = _tool_results(run)
    assert py_marker in results
    assert ts_marker not in results
    assert record_locations(run.session_id) == [str(py_rule)]


def test_error_when_location_unreadable(
    tmp_path: Path,
    make_index: Callable[..., Path],
    configure_index: Callable[[Path | str], None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
) -> None:
    """取得できない場所を渡すと、場所と理由を受け取り、既読にならない（異常シナリオ）。"""
    # 準備
    missing = tmp_path / "rules" / "missing.md"
    configure_index(make_index({"rule": str(missing)}))
    prompt = (
        f"MCP のツール read_rules を 1 回だけ呼んでください。locations に {missing} を渡し、"
        "session_id は渡さないでください。"
    )
    # 実行
    run = run_claude(prompt, allow=[READ_RULES_TOOL])
    # 検証
    results = _tool_results(run)
    assert str(missing) in results
    assert "failures" in results
    assert record_locations(run.session_id) == []


def test_normal_when_body_has_variables(
    make_rule: Callable[..., Path],
    make_index: Callable[..., Path],
    configure_index: Callable[..., None],
    run_claude: Callable[..., Any],
    record_locations: Callable[[str], list[str]],
    marker: Callable[[str], str],
) -> None:
    """本文の変数参照を展開し、未設定の名前を残して先頭に注釈が付く（正常シナリオ）。"""
    # 準備
    value = marker("SET-VALUE")
    rule = make_rule(
        "var.md",
        "# 規約\nset: !{E2E_SET_NAME}\nunset: !{E2E_UNSET_NAME}\n",
    )
    configure_index(make_index({"rule": str(rule)}), extra_env={"E2E_SET_NAME": value})
    prompt = (
        f"MCP のツール read_rules を 1 回だけ呼んでください。locations に {rule} を渡し、"
        "session_id は渡さないでください。"
    )
    # 実行
    run = run_claude(prompt, allow=[READ_RULES_TOOL])
    # 検証
    results = _tool_results(run)
    assert f"set: {value}" in results
    assert "!{E2E_SET_NAME}" not in results
    assert "unset: !{E2E_UNSET_NAME}" in results
    assert (
        '"body": "> 注釈: 次の変数参照は、環境変数が設定されていないため展開していない: '
        "E2E_UNSET_NAME\\n" in results
    )
    assert record_locations(run.session_id) == [str(rule)]
