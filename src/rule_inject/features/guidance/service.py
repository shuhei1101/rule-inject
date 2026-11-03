"""フックが返す案内文（止める案内・止めない案内・検索結果の案内・失敗の知らせ・作業の決まり）を組み立てる。"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from rule_inject.features.guidance.types import Guidance, GuidedReadTool, GuidedRule
from rule_inject.shared.errors import RuleInjectError

# 案内文 1 つの字数の上限
GUIDANCE_LIMIT = 10000
BLOCKING_HEADER = (
    "この操作に関連する未読のルールがあります。"
    "下のルールを参照してから、同じ操作をやり直してください。"
)
NON_BLOCKING_HEADER = (
    "この操作に関連する未読のルールがあります。"
    "必要に応じて下のルールを参照してください。"
    "この案内はルールごとにセッションで 1 回だけ表示します。"
)
WORK_RULES = (
    "新しいファイルは、まず Write で空の内容で作り、案内されたルールを読んでから Edit で中身を書いてください。"
    "空で作った時点で、そのファイルに当たるルールが案内されます。"
)
SEARCH_HEADER = (
    "検索結果のファイルに関連する未読のルールがあります（参照は任意です）。"
    "この案内はルールごとにセッションで 1 回だけ表示します。"
)
# 載せたルールに `ツール:` の行が 1 つでもあるときの 2 行目（参照の方法）
READ_TOOL_NOTE = (
    "`ツール:` の行があるルールは、そのツールで参照してください。"
    "記載の引数は全て指定し、「省略可」の引数とその他の引数は任意です。"
    "ツールが使えない場合と、`ツール:` の行が無いルールは、パスを Read で参照してください。"
)
# 載せたルールに `ツール:` の行が無いときの 2 行目（参照の方法）
READ_NOTE = "パスを Read で参照してください。"
# パスの行の下に置く参照するツールの行の頭
READ_TOOL_PREFIX = "  ツール: "


def _omitted_line(count: int) -> str:
    """載せきれなかったルールの件数の行を返す。"""
    return f"ほか {count} 件のルールは、上のルールを参照して操作をやり直したときに表示します。"


def _search_omitted_line(count: int) -> str:
    """検索結果の案内で載せきれなかったルールの件数の行を返す。"""
    return f"ほか {count} 件のルールは、次に関連したときに表示します。"


def _unchecked_line(count: int) -> str:
    """照合しなかった検索結果のパスの件数の行を返す。"""
    return f"検索結果のうち {count} 件は照合していません。"


def _json_text(value: Mapping[str, Any]) -> str:
    """引数のオブジェクトを、書いた順のキーの 1 行の JSON にする。"""
    return json.dumps(value, ensure_ascii=False)


def _tool_line(read_tool: GuidedReadTool) -> str:
    """参照するツール 1 つを `ツール:` の行にする（省略してよい引数があれば末尾に添える）。"""
    line = f"{READ_TOOL_PREFIX}{read_tool.tool} {_json_text(read_tool.args)}"
    if read_tool.optional_args:
        line += f"（省略可: {_json_text(read_tool.optional_args)}）"
    return line


def _assemble(
    header: str,
    rules: Sequence[GuidedRule],
    limit: int,
    omitted_line: Callable[[int], str],
    trailer: Sequence[str],
) -> Guidance:
    """冒頭・参照の方法の後に、ルールごとにパスの行とツールの行を、末尾の行を追加しても上限に収まるところまで載せる。"""
    # 参照の方法の行は、ツールの行を持つルールが 1 つでもあれば長い方の字数で見積もる
    has_tools = any(rule.read_tools for rule in rules)
    note_budget = len(READ_TOOL_NOTE if has_tools else READ_NOTE) + 1
    body: list[str] = []
    used = len(header) + note_budget + sum(len(line) + 1 for line in trailer)
    shown: list[str] = []
    shown_tools = False
    for index, rule in enumerate(rules):
        # パスの行とツールの行は 1 件として載せるか決める（途中では切らない）
        block = [f"- {rule.location}", *(_tool_line(read_tool) for read_tool in rule.read_tools)]
        size = sum(len(line) + 1 for line in block)
        remaining = len(rules) - (index + 1)
        # 次の 1 件と、残りがあるときの件数の行を追加しても上限に収まるかを見る
        tail = len(omitted_line(remaining)) + 1 if remaining else 0
        if used + size + tail > limit:
            break
        body.extend(block)
        shown.append(rule.location)
        shown_tools = shown_tools or bool(rule.read_tools)
        used += size
    # 載せきれなかったルールは件数だけを末尾に添える
    omitted = len(rules) - len(shown)
    if omitted:
        body.append(omitted_line(omitted))
    # 載せたルールにツールの行があるときだけ、ツールで参照する方法を伝える
    note = READ_TOOL_NOTE if shown_tools else READ_NOTE
    lines = [header, note, *body, *trailer]
    return Guidance(text="\n".join(lines), shown=tuple(shown))


def build_guidance(rules: Sequence[GuidedRule], *, limit: int = GUIDANCE_LIMIT) -> Guidance:
    """未読のルールのパスと参照するツールを、上限に収まる分だけ並べた案内文と、載せたパスを返す。"""
    # 止めるルールを先に、元の順を保って並べる
    ordered = [rule for rule in rules if rule.blocking] + [
        rule for rule in rules if not rule.blocking
    ]
    header = BLOCKING_HEADER if any(rule.blocking for rule in rules) else NON_BLOCKING_HEADER
    return _assemble(header, ordered, limit, _omitted_line, ())


def build_search_guidance(
    rules: Sequence[GuidedRule], *, unchecked: int = 0, limit: int = GUIDANCE_LIMIT
) -> Guidance:
    """検索で当たったファイルの未読・未案内のルールを、上限に収まる分だけ並べた案内文を返す（`blocking` は見ない）。"""
    # 照合しなかったパスがあれば、その件数を末尾に添える
    trailer = [_unchecked_line(unchecked)] if unchecked >= 1 else []
    return _assemble(SEARCH_HEADER, rules, limit, _search_omitted_line, trailer)


def build_failure_notice(
    summary: str,
    errors: Sequence[RuleInjectError],
    log_path: Path,
    *,
    limit: int = GUIDANCE_LIMIT,
) -> str:
    """索引・記録の読み書きの失敗を、場所と理由とログの場所つきの文にする。"""
    footer = f"詳しくはログ（{log_path}）を見てください。"
    lines = [summary]
    used = len(summary) + 1 + len(footer)
    for error in errors:
        line = f"- {error.path}: {error.reason}"
        # 上限を超える分は載せない（場所はログに残っている）
        if used + len(line) + 1 > limit:
            break
        lines.append(line)
        used += len(line) + 1
    lines.append(footer)
    return "\n".join(lines)
