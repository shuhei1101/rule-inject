"""エージェントフローの読み込みと SKILL.md の組み立て・書き出し。"""

from __future__ import annotations

import io
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from rule_inject.features.build_skills.types import BuiltSkill, SkillBuildError

# 生成の対象を探すリポジトリの直下からのフォルダ
FLOW_DIR = "docs/agent-flow"


def build_skills(root: Path) -> tuple[str, ...]:
    """全ての `type: skill` のエージェントフローから SKILL.md を組み立て、中身が違うものだけを書き出す。"""
    problems: list[str] = []
    built: list[BuiltSkill] = []
    loader = YAML(typ="safe")
    for path in sorted((root / FLOW_DIR).glob("*.yaml")):
        # 目次は生成の対象にしない
        if path.name == "index.yaml":
            continue
        source = path.relative_to(root).as_posix()
        try:
            flow = loader.load(path.read_text(encoding="utf-8"))
        except YAMLError as exc:
            # 読み込めない: 理由を記録して残りも確認する
            problems.append(f"{source}: {_one_line(str(exc))}")
            continue
        # スキルでないエージェントフローは対象にしない
        if not isinstance(flow, Mapping) or flow.get("type") != "skill":
            continue
        try:
            skill = render_skill(source, flow)
        except SkillBuildError as exc:
            problems.extend(exc.problems)
            continue
        # 書き出す先がリポジトリの外を指すか
        if not (root / skill.path).resolve().is_relative_to(root.resolve()):
            problems.append(f"{source}: skill.path")
            continue
        built.append(skill)
    # 1 件でも失敗したら、どのファイルも書き換えない
    if problems:
        raise SkillBuildError(tuple(problems))
    written: list[str] = []
    for skill in built:
        target = root / skill.path
        content = skill.content.encode("utf-8")
        # 中身が同じファイルは書き換えない
        if target.is_file() and target.read_bytes() == content:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(skill.path)
    return tuple(sorted(written))


def render_skill(source: str, flow: Mapping[str, object]) -> BuiltSkill:
    """1 つの `type: skill` のエージェントフローから SKILL.md を組み立てる。"""
    skill = _mapping(flow.get("skill"))
    steps = [_mapping(step) for step in _sequence(flow.get("steps"))]
    # 組み立てに要るキーを全て確認してから止める
    checks = (
        ("summary", bool(flow.get("summary"))),
        ("skill.path", bool(skill.get("path"))),
        ("steps[].name", bool(steps) and all(step.get("name") for step in steps)),
    )
    missing = tuple(f"{source}: {key}" for key, present in checks if not present)
    if missing:
        raise SkillBuildError(missing)
    path = str(skill["path"])
    arguments = [_mapping(argument) for argument in _sequence(skill.get("arguments"))]
    name = str(skill.get("name") or Path(path).parent.name)
    sections = [
        _frontmatter(flow, skill, arguments, name),
        f"<!-- {source} から生成した。このファイルを修正せず、設計書を修正して再生成する -->",
        f"# {flow.get('title') or name}",
    ]
    # 引数があるときだけ引数の表を配置する
    if arguments:
        rows = [f"| `${arg['name']}` | {arg.get('description', '')} |" for arg in arguments]
        sections.append("\n".join(["## 引数", "", "| 引数 | 説明 |", "| --- | --- |", *rows]))
    sections.append("## 手順")
    sections.extend(_step_section(step) for step in steps)
    return BuiltSkill(path=path, content="\n\n".join(sections) + "\n")


def _frontmatter(
    flow: Mapping[str, object],
    skill: Mapping[str, object],
    arguments: Sequence[Mapping[str, object]],
    name: str,
) -> str:
    """frontmatter を決まった並びで組み立て、`---` で囲む。"""
    values: dict[str, object] = {"name": name, "description": flow["summary"]}
    hints = [str(argument["hint"]) for argument in arguments if argument.get("hint")]
    # 値が無いキーは配置しない
    if hints:
        values["argument-hint"] = " ".join(hints)
    if arguments:
        values["arguments"] = [str(argument["name"]) for argument in arguments]
    allowed_tools = _sequence(skill.get("allowed_tools"))
    if allowed_tools:
        values["allowed-tools"] = list(allowed_tools)
    values.update(_mapping(skill.get("frontmatter")))
    return f"---\n{_dump(values, flow_style=False)}---"


def _step_section(step: Mapping[str, object]) -> str:
    """1 つの工程を `### {name}` のセクションにする。"""
    parts = [f"### {step['name']}"]
    # 実行の条件があるときだけ条件の行を配置する
    if step.get("when"):
        parts.append(f"{step['when']}だけ行う。")
    if step.get("body"):
        parts.append(str(step["body"]).rstrip("\n"))
    calls = [_mapping(call) for call in _sequence(step.get("calls"))]
    if calls:
        parts.append("\n".join(["呼ぶもの:", *(f"- {_call_line(call)}" for call in calls)]))
    return "\n\n".join(parts)


def _call_line(call: Mapping[str, object]) -> str:
    """呼ぶもの 1 件を、種類ごとの書き方の 1 行にする。"""
    kind = call.get("type")
    # 種類ごとに呼ぶ先の書き方を決める
    if kind == "mcp":
        line = f"MCP `{call.get('server')}` の `{call.get('tool')}`"
    elif kind == "tool":
        line = f"ツール `{call.get('tool')}`"
    elif kind == "command":
        line = f"コマンド `{call.get('command')}`"
    elif kind == "skill":
        line = f"スキル `{call.get('skill')}`"
    else:
        line = f"エージェントフロー `{call.get('flow')}`"
    # 引数があれば 1 行の YAML を添える
    if call.get("args"):
        line += f" `{_dump(call['args'], flow_style=True).strip()}`"
    return line


def _dump(value: object, *, flow_style: bool) -> str:
    """値を、折り返さずにキーの順を保った YAML の文字列にする。"""
    dumper = YAML(typ="safe")
    dumper.default_flow_style = flow_style
    dumper.allow_unicode = True
    dumper.width = sys.maxsize
    dumper.representer.sort_base_mapping_type_on_output = False
    stream = io.StringIO()
    dumper.dump(value, stream)
    return stream.getvalue()


def _mapping(value: object) -> Mapping[str, object]:
    """辞書でない値を空の辞書として扱う。"""
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    """配列でない値を空の配列として扱う。"""
    return value if isinstance(value, list) else []


def _one_line(text: str) -> str:
    """複数行の理由を 1 行にまとめる。"""
    return " ".join(text.split())
