"""フックが返却する案内文（止める案内・止めない案内・検索結果の案内・失敗の通知）を組み立てる。"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from rule_inject.features.guidance.types import Guidance, GuidedReadTool, GuidedRule
from rule_inject.shared.errors import RuleInjectError
from rule_inject.shared.prompts import load_hook_prompt

# 案内文 1 つの字数の上限
GUIDANCE_LIMIT = 10000
# 以下はフックのプロンプトファイルの名前（文面は `load_hook_prompt` で描画する）
BLOCKING_HEADER = "guide-blocking-header"
NON_BLOCKING_HEADER = "guide-non-blocking-header"
# サーバーの起動の補助が起動を依頼したときの文面（変数 `service`）
SERVER_START_NOTICE = "server-start"
SEARCH_HEADER = "search-header"
# 記載したルールに `ツール:` の行が 1 つでもあるときの 2 行目（参照の方法）
READ_TOOL_NOTE = "read-tool-note"
# 記載したルールに `ツール:` の行が無いときの 2 行目（参照の方法）
READ_NOTE = "read-note"
# 参照するツールの行（変数 `tool`・`args`・`optional_args`）
TOOL_LINE = "tool-line"
# 記載しきれなかったルールの件数の行（変数 `count`）
OMITTED_LINE = "guide-omitted"
SEARCH_OMITTED_LINE = "search-omitted"
# 照合しなかった検索結果の件数の行（変数 `count`）
UNCHECKED_LINE = "search-unchecked"
# 失敗の通知の末尾のログの場所の行（変数 `log_path`）
FAILURE_FOOTER = "failure-footer"
# `build_failure_notice` へ引き渡す、何が起きたかの 1 文
INDEX_FAILURE = "failure-index"
RECORD_READ_FAILURE = "failure-read-record"
GUIDED_READ_FAILURE = "failure-read-guided"
GUIDED_WRITE_FAILURE = "failure-write-guided"
# パスの行の下に配置する参照するツールの行の字下げ
READ_TOOL_PREFIX = "  "


def _omitted_line(count: int) -> str:
    """記載しきれなかったルールの件数の行を返却する。"""
    return load_hook_prompt(OMITTED_LINE, {"count": count})


def _search_omitted_line(count: int) -> str:
    """検索結果の案内で記載しきれなかったルールの件数の行を返却する。"""
    return load_hook_prompt(SEARCH_OMITTED_LINE, {"count": count})


def _unchecked_line(count: int) -> str:
    """照合しなかった検索結果のパスの件数の行を返却する。"""
    return load_hook_prompt(UNCHECKED_LINE, {"count": count})


def _json_text(value: Mapping[str, Any]) -> str:
    """引数のオブジェクトを、記載した順のキーの 1 行の JSON にする。"""
    return json.dumps(value, ensure_ascii=False)


def _tool_line(read_tool: GuidedReadTool) -> str:
    """参照するツール 1 つを `ツール:` の行にする（省略してよい引数があれば末尾に添える）。"""
    optional_args = _json_text(read_tool.optional_args) if read_tool.optional_args else ""
    line = load_hook_prompt(
        TOOL_LINE,
        {
            "tool": read_tool.tool,
            "args": _json_text(read_tool.args),
            "optional_args": optional_args,
        },
    )
    return f"{READ_TOOL_PREFIX}{line}"


def _assemble(
    header: str,
    rules: Sequence[GuidedRule],
    limit: int,
    omitted_line: Callable[[int], str],
    trailer: Sequence[str],
) -> Guidance:
    """冒頭・参照の方法の後に、ルールごとにパスの行とツールの行を、末尾の行を追加しても上限に収まるところまで記載する。"""
    # 参照の方法の行は、ツールの行を持つルールが 1 つでもあれば長い方の字数で見積もる
    has_tools = any(rule.read_tools for rule in rules)
    note_budget = len(load_hook_prompt(READ_TOOL_NOTE if has_tools else READ_NOTE)) + 1
    body: list[str] = []
    used = len(header) + note_budget + sum(len(line) + 1 for line in trailer)
    shown: list[str] = []
    shown_tools = False
    for index, rule in enumerate(rules):
        # パスの行とツールの行は 1 件として記載するか決める（途中では切らない）
        block = [f"- {rule.location}", *(_tool_line(read_tool) for read_tool in rule.read_tools)]
        size = sum(len(line) + 1 for line in block)
        remaining = len(rules) - (index + 1)
        # 次の 1 件と、残りがあるときの件数の行を追加しても上限に収まるかを確認する
        tail = len(omitted_line(remaining)) + 1 if remaining else 0
        if used + size + tail > limit:
            break
        body.extend(block)
        shown.append(rule.location)
        shown_tools = shown_tools or bool(rule.read_tools)
        used += size
    # 記載しきれなかったルールは件数だけを末尾に添える
    omitted = len(rules) - len(shown)
    if omitted:
        body.append(omitted_line(omitted))
    # 記載したルールにツールの行があるときだけ、ツールで参照する方法を伝える
    note = load_hook_prompt(READ_TOOL_NOTE if shown_tools else READ_NOTE)
    lines = [header, note, *body, *trailer]
    return Guidance(text="\n".join(lines), shown=tuple(shown))


def build_guidance(rules: Sequence[GuidedRule], *, limit: int = GUIDANCE_LIMIT) -> Guidance:
    """未読のルールのパスと参照するツールを、上限に収まる分だけ並べた案内文と、記載したパスを返却する。"""
    # 止めるルールを先に、元の順を保って並べる
    ordered = [rule for rule in rules if rule.blocking] + [
        rule for rule in rules if not rule.blocking
    ]
    header = load_hook_prompt(
        BLOCKING_HEADER if any(rule.blocking for rule in rules) else NON_BLOCKING_HEADER
    )
    return _assemble(header, ordered, limit, _omitted_line, ())


def build_search_guidance(
    rules: Sequence[GuidedRule], *, unchecked: int = 0, limit: int = GUIDANCE_LIMIT
) -> Guidance:
    """検索で該当したファイルの未読・未案内のルールを、上限に収まる分だけ並べた案内文を返却する（`blocking` は確認しない）。"""
    # 照合しなかったパスがあれば、その件数を末尾に添える
    trailer = [_unchecked_line(unchecked)] if unchecked >= 1 else []
    return _assemble(load_hook_prompt(SEARCH_HEADER), rules, limit, _search_omitted_line, trailer)


def build_server_start_notice(service: str) -> str:
    """`SERVER_START_NOTICE` をサービス名で描画した文面を返却する。"""
    return load_hook_prompt(SERVER_START_NOTICE, {"service": service})


def build_failure_notice(
    summary: str,
    errors: Sequence[RuleInjectError],
    log_path: Path,
    *,
    summary_values: Mapping[str, object] | None = None,
    limit: int = GUIDANCE_LIMIT,
) -> str:
    """索引・記録の読み込み・書き込みの失敗を、`summary` のプロンプトの本文と場所と理由とログの場所つきの文にする。"""
    footer = load_hook_prompt(FAILURE_FOOTER, {"log_path": log_path})
    summary_text = load_hook_prompt(summary, summary_values)
    lines = [summary_text]
    used = len(summary_text) + 1 + len(footer)
    for error in errors:
        line = f"- {error.path}: {error.reason}"
        # 上限を超える分は記載しない（場所はログに残っている）
        if used + len(line) + 1 > limit:
            break
        lines.append(line)
        used += len(line) + 1
    lines.append(footer)
    return "\n".join(lines)
