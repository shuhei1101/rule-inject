"""索引のチェックと、書き込む前と書き込んだ後の問題の比較。"""

from __future__ import annotations

import io
import re
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rule_inject.features.index import read_index_text
from rule_inject.features.index.check.types import IndexCheck, IndexProblem
from rule_inject.features.index.types import EntryOutcome
from rule_inject.shared.errors import IndexReadError, describe
from rule_inject.shared.variables import expand_variables

if TYPE_CHECKING:
    from jsonschema.protocols import Validator

# 索引の JSON Schema のファイル名（このパッケージに同梱する）
INDEX_SCHEMA_FILE = "index.schema.yaml"
# 問題が索引全体にかかるときの場所
ROOT_LOCATION = "$"
# エントリの場所の先頭（`rules[位置]`）
ENTRY_LOCATION_PATTERN = re.compile(r"^rules\[[0-9]+\]")
ENTRY_LOCATION_PLACEHOLDER = "rules[]"
RULES_KEY = "rules"
# `check_entry` が組み立てた索引の、そのエントリの場所の先頭
ENTRY_PREFIX = "rules[0]"
RULE_KEY = "rule"
# エントリ 1 件の索引を書き出す YAML の書式（フックの読み取りが受け付けるブロック形式）
ENTRY_YAML_WIDTH = 4096
ENTRY_MAPPING_INDENT = 2
ENTRY_SEQUENCE_INDENT = 4
ENTRY_SEQUENCE_OFFSET = 2
# 変数参照を展開できないエントリで除く問題の種類（ルールの場所を解けないため）
UNRESOLVED_DROPPED_KINDS = ("skipped_entry", "missing_rule")


def load_validator() -> Validator:
    """パッケージに同梱した索引の JSON Schema を読み、検証器を作る。"""
    text = (
        resources.files("rule_inject.features.index.check")
        .joinpath(INDEX_SCHEMA_FILE)
        .read_text(encoding="utf-8")
    )
    schema = YAML(typ="safe").load(text)
    # Schema 自体が Schema として正しいことを確認する
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _hook_error(index_path: str, reason: str) -> IndexCheck:
    """フックが読めない理由だけを持つ結果を作る。"""
    problem = IndexProblem(
        kind="hook_error", location=ROOT_LOCATION, reason=reason, position=None, rev=None
    )
    return IndexCheck(index=index_path, problems=(problem,))


def check_index(index_path: str, env: Mapping[str, str], *, validator: Validator) -> IndexCheck:
    """索引のファイルを読み、`check_index_text` で確認する。"""
    try:
        text = Path(index_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        # フックが読めない理由と同じ文言にする
        return _hook_error(index_path, describe(exc))
    return check_index_text(index_path, text, env, validator=validator)


def _format_location(path: list[str | int]) -> str:
    """違反の場所（`absolute_path`）を、キーは `.`、リストの要素は `[位置]` で結んだ文字列にする。"""
    location = ""
    for part in path:
        if isinstance(part, int):
            location += f"[{part}]"
        else:
            location += f".{part}" if location else part
    return location or ROOT_LOCATION


def _location_order(path: list[str | int]) -> list[tuple[int, str]]:
    """違反を場所の順に並べるための、数と文字を混ぜて比べられる並べ替えの鍵を返却する。"""
    return [(part if isinstance(part, int) else -1, str(part)) for part in path]


def _violations(
    text: str, outcomes: tuple[EntryOutcome, ...], validator: Validator
) -> list[IndexProblem]:
    """JSON Schema への違反を、場所の順に全て並べる。"""
    try:
        document = YAML(typ="safe").load(text)
    except YAMLError as exc:
        # フックは読めるが YAML としては読めない内容は、索引全体の違反にする
        return [
            IndexProblem(
                kind="violation",
                location=ROOT_LOCATION,
                reason=describe(exc),
                position=None,
                rev=None,
            )
        ]
    problems: list[IndexProblem] = []
    for error in sorted(
        validator.iter_errors(document), key=lambda err: _location_order(list(err.absolute_path))
    ):
        path = list(error.absolute_path)
        # `rules` の中の違反は、そのエントリの位置とバージョンを持たせる
        entry_position = (
            path[1]
            if path[:1] == [RULES_KEY] and len(path) > 1 and isinstance(path[1], int)
            else None
        )
        outcome = (
            outcomes[entry_position]
            if entry_position is not None and entry_position < len(outcomes)
            else None
        )
        problems.append(
            IndexProblem(
                kind="violation",
                location=_format_location(path),
                reason=error.message,
                position=entry_position if outcome is not None else None,
                rev=outcome.rev if outcome is not None else None,
            )
        )
    return problems


def check_index_text(
    index_path: str, text: str, env: Mapping[str, str], *, validator: Validator
) -> IndexCheck:
    """索引の内容を、フックと同じ読み取り→ JSON Schema → ルールの場所の実在の順に確認する。"""
    # フックが読めない索引は、その理由だけを返却する（JSON Schema に照らさず、ルールの場所も確認しない）
    try:
        content = read_index_text(index_path, text, env)
    except IndexReadError as exc:
        return _hook_error(index_path, exc.reason)
    problems = _violations(text, content.outcomes, validator)
    # 照合に使用するエントリのうち、解いたルールの場所にファイルが無いもの（無効のエントリは確認しない）
    problems.extend(
        IndexProblem(
            kind="missing_rule",
            location=f"rules[{outcome.position}].rule",
            reason=outcome.entry.location,
            position=outcome.position,
            rev=outcome.rev,
        )
        for outcome in content.outcomes
        if outcome.status == "effective"
        and outcome.entry is not None
        and not Path(outcome.entry.location).is_file()
    )
    # フックが読み飛ばすエントリ（場所を解けないため、ファイルの有無は確認しない）
    problems.extend(
        IndexProblem(
            kind="skipped_entry",
            location=f"rules[{outcome.position}]",
            reason=outcome.reason or "",
            position=outcome.position,
            rev=outcome.rev,
        )
        for outcome in content.outcomes
        if outcome.status == "skipped"
    )
    return IndexCheck(index=index_path, problems=tuple(problems))


def _problem_key(problem: IndexProblem) -> tuple[str, str | None, str, str]:
    """書き込む前と書き込んだ後で同じ問題かを比べる鍵を返却する（位置は新規作成・削除でずれるため比べない）。"""
    location = ENTRY_LOCATION_PATTERN.sub(ENTRY_LOCATION_PLACEHOLDER, problem.location)
    return (problem.kind, problem.rev, location, problem.reason)


def new_problems(
    before: IndexCheck, after: IndexCheck, changed_rev: str | None
) -> tuple[IndexProblem, ...]:
    """書き込んだ後の索引の問題のうち、書き込む前に無かったものを返却する。"""
    # 書き込んだ後にフックが読めなければ、それだけを返却する（書き込む前も読めなかった場合も含む）
    hook_errors = tuple(problem for problem in after.problems if problem.kind == "hook_error")
    if hook_errors:
        return hook_errors
    existing = {_problem_key(problem) for problem in before.problems}
    # 書き込んだエントリの問題は、書き込む前に同じ理由があっても新しい問題として扱う
    return tuple(
        problem
        for problem in after.problems
        if (changed_rev is not None and problem.rev == changed_rev)
        or _problem_key(problem) not in existing
    )


def check_change(
    index_path: str,
    before_text: str,
    after_text: str,
    changed_rev: str | None,
    *,
    env: Mapping[str, str],
    validator: Validator,
) -> tuple[str, ...]:
    """書き込む前と書き込んだ後の索引を確認し、新しく出た問題を `{索引の中の場所}: {理由}` の行で返却する。"""
    before = check_index_text(index_path, before_text, env, validator=validator)
    after = check_index_text(index_path, after_text, env, validator=validator)
    return tuple(
        f"{problem.location}: {problem.reason}"
        for problem in new_problems(before, after, changed_rev)
    )


def _entry_index_text(entry: Mapping[str, object]) -> str:
    """エントリ 1 件だけの索引を、フックの読み取りが受け付けるブロック形式の文字列にする。"""
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.width = ENTRY_YAML_WIDTH
    yaml.indent(
        mapping=ENTRY_MAPPING_INDENT, sequence=ENTRY_SEQUENCE_INDENT, offset=ENTRY_SEQUENCE_OFFSET
    )
    stream = io.StringIO()
    yaml.dump({RULES_KEY: [dict(entry)]}, stream)
    return stream.getvalue()


def _entry_location(location: str) -> str:
    """索引の中の場所を、エントリの中の場所にする（エントリ全体は `ROOT_LOCATION`）。"""
    if location == ENTRY_PREFIX:
        return ROOT_LOCATION
    if location.startswith(f"{ENTRY_PREFIX}."):
        return location[len(ENTRY_PREFIX) + 1 :]
    return location


def check_entry(
    index_path: str,
    entry: Mapping[str, object],
    env: Mapping[str, str],
    *,
    validator: Validator,
) -> tuple[IndexProblem, ...]:
    """エントリ 1 件だけの索引を `check_index_text` で確認し、場所をエントリの中の場所にした問題を返却する。"""
    result = check_index_text(index_path, _entry_index_text(entry), env, validator=validator)
    problems = result.problems
    # `validators[]` の実行環境にはセッションの環境変数が届かないため、展開できない変数参照は違反にしない
    rule = entry.get(RULE_KEY)
    if isinstance(rule, str) and expand_variables(rule, env).unresolved:
        problems = tuple(
            problem for problem in problems if problem.kind not in UNRESOLVED_DROPPED_KINDS
        )
    return tuple(
        IndexProblem(
            kind=problem.kind,
            location=_entry_location(problem.location),
            reason=problem.reason,
            position=problem.position,
            rev=problem.rev,
        )
        for problem in problems
    )
