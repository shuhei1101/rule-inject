"""ルールの本文の読み込みと、応答の上限への収め方。"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType

from rule_inject.features.fetch.client import FETCH_TIMEOUT_SEC, FetchError, fetch_url
from rule_inject.features.fetch.types import (
    FetchFailure,
    FetchUrlFn,
    ReadRulesResult,
    RulePage,
)
from rule_inject.shared.errors import describe
from rule_inject.shared.paths import URL_SCHEMES
from rule_inject.shared.variables import expand_variables

# 応答の JSON 全体の字数の上限（`anthropic/maxResultSizeChars` にも同じ値を付ける）
MAX_RESULT_CHARS = 40000
# 展開していない変数参照を本文の先頭で知らせる 1 行の形（`{names}` に名前を並べて入れる）
UNRESOLVED_NOTE = "> 注釈: 次の変数参照は、環境変数が設定されていないため展開していない: {names}"
NAME_SEPARATOR = "、"
# 環境変数を渡されないときの、変数参照を 1 つも展開しない環境変数
NO_ENV: Mapping[str, str] = MappingProxyType({})


def render_result(result: ReadRulesResult) -> str:
    """ReadRulesResult を、日本語をエスケープしない応答の JSON 文字列にする。履歴に書けなかった場所が無ければ history_failures は出さない。"""
    payload = dataclasses.asdict(result)
    if not result.history_failures:
        del payload["history_failures"]
    return json.dumps(payload, ensure_ascii=False)


def _read_body(location: str, fetch: FetchUrlFn) -> str:
    """場所の本文を読む（URL は fetch、それ以外は UTF-8 のファイル）。失敗は例外で知らせる。"""
    if location.startswith(URL_SCHEMES):
        return fetch(location, FETCH_TIMEOUT_SEC)
    return Path(location).read_text(encoding="utf-8")


def expand_body(body: str, env: Mapping[str, str]) -> str:
    """本文の変数参照を展開し、展開できなかった名前があれば先頭に注釈を 1 行足す。"""
    expansion = expand_variables(body, env)
    # 全て展開できたら、注釈を足さない
    if not expansion.unresolved:
        return expansion.text
    note = UNRESOLVED_NOTE.format(names=NAME_SEPARATOR.join(expansion.unresolved))
    return f"{note}\n{expansion.text}"


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


def collect_pages(
    locations: Sequence[str],
    *,
    failures: Sequence[FetchFailure] = (),
    fetch: FetchUrlFn = fetch_url,
    limit: int = MAX_RESULT_CHARS,
    env: Mapping[str, str] = NO_ENV,
) -> ReadRulesResult:
    """場所ごとに本文を読んで変数参照を展開し、応答の上限に収めて返す。"""
    # 呼び出し元が先に決めた failures を先頭に置き、上限の計算に含める
    all_failures = list(failures)
    bodies: list[tuple[str, str]] = []
    for location in locations:
        # 読めなかった場所は理由を添えて failures へ回す（再試行はしない）
        try:
            bodies.append((location, expand_body(_read_body(location, fetch), env)))
        except FetchError as exc:
            all_failures.append(FetchFailure(location=location, reason=exc.reason))
        except (OSError, ValueError) as exc:
            all_failures.append(FetchFailure(location=location, reason=describe(exc)))
    return _fit_to_limit(bodies, all_failures, limit)
