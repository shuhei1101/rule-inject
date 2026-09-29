"""read_rules の中身（本文の読み込み・応答の上限・既読の記録）。"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Sequence
from pathlib import Path

from rule_inject.features.fetch.client import FETCH_TIMEOUT_SEC, FetchError, fetch_url
from rule_inject.features.fetch.types import (
    FetchFailure,
    FetchUrlFn,
    ReadRulesResult,
    RulePage,
)
from rule_inject.features.index.service import match_path, rule_locations
from rule_inject.features.index.types import IndexEntry
from rule_inject.features.record.service import append_record, is_valid_session_id
from rule_inject.shared.errors import describe
from rule_inject.shared.paths import URL_SCHEMES, resolve_location

# 応答の JSON 全体の字数の上限（`anthropic/maxResultSizeChars` にも同じ値を付ける）
MAX_RESULT_CHARS = 40000
NOT_IN_INDEX_REASON = "索引に載っていない場所"


class ToolArgumentError(ValueError):
    """session_id が無い・形が外れている、または locations と paths が空。"""


def render_result(result: ReadRulesResult) -> str:
    """ReadRulesResult を、日本語をエスケープしない応答の JSON 文字列にする。"""
    return json.dumps(dataclasses.asdict(result), ensure_ascii=False)


def _target_locations(
    locations: Sequence[str],
    paths: Sequence[str],
    entries: Sequence[IndexEntry],
    failures: list[FetchFailure],
) -> list[str]:
    """本文を取りに行く場所を並べる。索引に載っていない場所は failures へ回す。"""
    base = Path.cwd()
    listed = rule_locations(entries)
    targets: list[str] = []
    # 場所で引く: 索引に載ったルールの場所だけを読む
    for location in locations:
        resolved = resolve_location(location, base)
        if resolved in listed:
            targets.append(resolved)
        else:
            failures.append(FetchFailure(location=resolved, reason=NOT_IN_INDEX_REASON))
    # 対象のパスで引く: 読む操作として当たるルールの場所を足す
    for path in paths:
        targets.extend(
            rule.location for rule in match_path(entries, resolve_location(path, base), "read")
        )
    # 重なりは 1 つにする（並びは保つ）
    return list(dict.fromkeys(targets))


def _read_body(location: str, fetch: FetchUrlFn) -> str:
    """場所の本文を読む（URL は fetch、それ以外は UTF-8 のファイル）。失敗は例外で知らせる。"""
    if location.startswith(URL_SCHEMES):
        return fetch(location, FETCH_TIMEOUT_SEC)
    return Path(location).read_text(encoding="utf-8")


def _fit_to_limit(
    bodies: Sequence[tuple[str, str]], failures: list[FetchFailure], limit: int
) -> ReadRulesResult:
    """応答が上限に収まる分だけ本文を載せ、収まらない場所は次に回す。"""
    # 1 件だけでも収まらない本文は、次の呼び出しでも返せないため取得できなかった場所にする
    fitting: list[RulePage] = []
    for location, body in bodies:
        page = RulePage(location=location, body=body)
        if len(render_result(ReadRulesResult(pages=[page]))) > limit:
            failures.append(
                FetchFailure(location=location, reason=f"1 件で応答の上限（{limit} 字）を超える")
            )
        else:
            fitting.append(page)
    pages: list[RulePage] = []
    deferred: list[str] = []
    for index, page in enumerate(fitting):
        # まだ判定していない場所は、収まらなければ deferred に回る。最終の応答に入る形で数える
        pending = [later.location for later in fitting[index + 1 :]]
        candidate = ReadRulesResult(
            pages=[*pages, page], deferred=[*deferred, *pending], failures=failures
        )
        if len(render_result(candidate)) <= limit:
            pages.append(page)
        elif pages:
            # 載せた本文がある: 次の呼び出しで取得する場所として回す
            deferred.append(page.location)
        else:
            # 1 件も載せていない: deferred に回すと呼び直しても進まないため、理由つきで failures へ回す
            failures.append(
                FetchFailure(
                    location=page.location,
                    reason=(
                        f"ほかの場所と合わせると応答の上限（{limit} 字）を超える。"
                        "この場所だけを locations に渡して取り直す"
                    ),
                )
            )
    return ReadRulesResult(pages=pages, deferred=deferred, failures=failures)


def read_rules(
    locations: Sequence[str],
    paths: Sequence[str],
    session_id: str | None,
    *,
    entries: Sequence[IndexEntry],
    state_dir: Path,
    fetch: FetchUrlFn = fetch_url,
    limit: int = MAX_RESULT_CHARS,
) -> ReadRulesResult:
    """索引に載ったルールの本文を集め、上限に収めて返し、返した場所を既読にする。"""
    # 引数が足りなければ、何も読まずにエラーにする
    if session_id is None or not is_valid_session_id(session_id):
        raise ToolArgumentError("session_id が無いか、形が外れています（フックが足す値です）")
    if not locations and not paths:
        raise ToolArgumentError("locations と paths のどちらかに、場所かパスを渡してください")
    failures: list[FetchFailure] = []
    bodies: list[tuple[str, str]] = []
    for location in _target_locations(locations, paths, entries, failures):
        # 読めなかった場所は理由を添えて failures へ回す（再試行も既読もしない）
        try:
            bodies.append((location, _read_body(location, fetch)))
        except FetchError as exc:
            failures.append(FetchFailure(location=location, reason=exc.reason))
        except (OSError, ValueError) as exc:
            failures.append(FetchFailure(location=location, reason=describe(exc)))
    result = _fit_to_limit(bodies, failures, limit)
    # 返した本文の場所だけを既読にする
    append_record(state_dir, session_id, [page.location for page in result.pages])
    return result
