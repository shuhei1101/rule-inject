"""フックが返す案内文（止める案内・止めない案内・検索結果の案内・失敗の知らせ・作業の決まり）を組み立てる。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from rule_inject.features.guidance.types import Guidance, GuidedRule
from rule_inject.shared.errors import RuleInjectError

# 案内文 1 つの字数の上限
GUIDANCE_LIMIT = 10000
BLOCKING_HEADER = (
    "操作の対象に当たる未読のルールがあります。"
    "read_rules に下の場所を渡して本文を取得してから、同じ操作をやり直してください。"
)
NON_BLOCKING_HEADER = (
    "操作の対象に当たる未読のルールがあります。"
    "必要に応じて read_rules に下の場所を渡して本文を読んでください。"
    "この案内はルールごとにセッションで 1 回だけ出ます。"
)
WORK_RULES = (
    "新しいファイルは、まず Write で空の内容で作り、案内されたルールを読んでから Edit で中身を書いてください。"
    "空で作った時点で、そのファイルに当たるルールが案内されます。"
)
SEARCH_HEADER = (
    "検索で当たったファイルに未読のルールがあります（読むかは任意です）。"
    "読む場合は read_rules に下の場所を渡して本文を取得してください。"
    "この案内はルールごとにセッションで 1 回だけ出ます。"
)


def _omitted_line(count: int) -> str:
    """載せきれなかったルールの件数の行を返す。"""
    return f"ほか {count} 件のルールは、上のルールを読んで操作をやり直したときに案内します。"


def _search_omitted_line(count: int) -> str:
    """検索結果の案内で載せきれなかったルールの件数の行を返す。"""
    return f"ほか {count} 件のルールは、次に当たったときに案内します。"


def _unchecked_line(count: int) -> str:
    """照合しなかった検索結果のパスの件数の行を返す。"""
    return f"検索結果のうち {count} 件は照合していません。"


def _assemble(
    header: str,
    locations: Sequence[str],
    limit: int,
    omitted_line: Callable[[int], str],
    trailer: Sequence[str],
) -> Guidance:
    """冒頭の後に場所を 1 行ずつ、末尾の行を足しても上限に収まるところまで載せる。"""
    lines = [header]
    used = len(header) + sum(len(line) + 1 for line in trailer)
    shown: list[str] = []
    for index, location in enumerate(locations):
        line = f"- {location}"
        remaining = len(locations) - (index + 1)
        # 次の 1 行と、残りがあるときの件数の行を足しても上限に収まるかを見る
        tail = len(omitted_line(remaining)) + 1 if remaining else 0
        if used + len(line) + 1 + tail > limit:
            break
        lines.append(line)
        shown.append(location)
        used += len(line) + 1
    # 載せきれなかったルールは件数だけを末尾に添える
    omitted = len(locations) - len(shown)
    if omitted:
        lines.append(omitted_line(omitted))
    lines.extend(trailer)
    return Guidance(text="\n".join(lines), shown=tuple(shown))


def build_guidance(rules: Sequence[GuidedRule], *, limit: int = GUIDANCE_LIMIT) -> Guidance:
    """未読のルールの場所を、上限に収まる分だけ並べた案内文と、載せた場所を返す。"""
    # 止めるルールを先に、元の順を保って並べる
    ordered = [rule for rule in rules if rule.blocking] + [
        rule for rule in rules if not rule.blocking
    ]
    header = BLOCKING_HEADER if any(rule.blocking for rule in rules) else NON_BLOCKING_HEADER
    return _assemble(header, [rule.location for rule in ordered], limit, _omitted_line, ())


def build_search_guidance(
    locations: Sequence[str], *, unchecked: int = 0, limit: int = GUIDANCE_LIMIT
) -> Guidance:
    """検索で当たったファイルの未読・未案内のルールの場所を、上限に収まる分だけ並べた案内文を返す。"""
    # 照合しなかったパスがあれば、その件数を末尾に添える
    trailer = [_unchecked_line(unchecked)] if unchecked >= 1 else []
    return _assemble(SEARCH_HEADER, locations, limit, _search_omitted_line, trailer)


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
