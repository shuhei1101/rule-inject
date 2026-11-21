"""features/build_skills/service.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

FLOW_A = """\
type: skill
title: a のスキル
summary: a を実行する
skill:
  path: skills/a/SKILL.md
steps:
  - name: 実行する
    body: a を実行する。
"""

FLOW_B = """\
type: skill
title: b
summary: b のスキル
skill:
  path: skills/b/SKILL.md
steps:
  - name: 手順 1
    body: 実行する。
"""

SKILL_B = """\
---
name: b
description: b のスキル
---

<!-- docs/agent-flow/b.yaml から生成した。このファイルを修正せず、設計書を修正して再生成する -->

# b

## 手順

### 手順 1

実行する。
"""

FLOW_C = """\
title: c
summary: c の流れ
skill:
  path: skills/c/SKILL.md
steps:
  - name: 実行する
    body: c を実行する。
"""

LONG_DESCRIPTION = (
    "リポジトリの索引が rule-inject に読まれる状態にして、索引のチェックの結果を示し、"
    "端末の設定が無ければ端末のセットアップを案内して止まるスキルで、"
    "索引を登録し直すときと索引のチェックの結果を確認したいときに使用する"
)

SKILL_DEMO = f"""\
---
name: demo
description: {LONG_DESCRIPTION}
argument-hint: '[索引のパス]'
arguments:
- index
---

<!-- docs/agent-flow/demo.yaml から生成した。このファイルを修正せず、設計書を修正して再生成する -->

# デモ

## 引数

| 引数 | 説明 |
| --- | --- |
| `$index` | 索引のパス |

## 手順

### 確認する

`$index` を指定したときだけ行う。

索引を確認する。

呼ぶもの:
- MCP `MCP-122-1#` の `check_indexes` `{{required: [project_dir]}}`
- ツール `AskUserQuestion`

### 結果を示す

結果を示す。
"""


@pytest.fixture
def write_flow(tmp_path: Path) -> Callable[[str, str], Path]:
    """一時フォルダの `docs/agent-flow/` にエージェントフローを書き込む関数を返却する。"""

    def write(name: str, text: str) -> Path:
        """`docs/agent-flow/{name}` に `text` を書き込む。"""
        path = tmp_path / "docs" / "agent-flow" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return write


def test_build_skills(tmp_path: Path, write_flow: Callable[[str, str], Path]) -> None:
    """中身が違う SKILL.md だけを書き出す（正常系）。"""
    from rule_inject.features.build_skills.service import build_skills

    # 準備
    write_flow("a.yaml", FLOW_A)
    write_flow("b.yaml", FLOW_B)
    write_flow("c.yaml", FLOW_C)
    write_flow("index.yaml", "items: []\n")
    skill_b = tmp_path / "skills" / "b" / "SKILL.md"
    skill_b.parent.mkdir(parents=True)
    skill_b.write_bytes(SKILL_B.encode("utf-8"))
    # 実行
    result = build_skills(tmp_path)
    # 検証
    assert result == ("skills/a/SKILL.md",)
    assert (tmp_path / "skills" / "a" / "SKILL.md").is_file()
    assert skill_b.read_bytes() == SKILL_B.encode("utf-8")
    assert not (tmp_path / "skills" / "c").exists()


def test_build_skills_when_unreadable(
    tmp_path: Path, write_flow: Callable[[str, str], Path]
) -> None:
    """読み込めないエージェントフローがある（異常系）。"""
    from rule_inject.features.build_skills.service import build_skills
    from rule_inject.features.build_skills.types import SkillBuildError

    # 準備
    write_flow("a.yaml", FLOW_A)
    write_flow("c.yaml", 'title: "c\n')
    # 実行
    with pytest.raises(SkillBuildError) as caught:
        build_skills(tmp_path)
    # 検証
    assert len(caught.value.problems) == 1
    assert caught.value.problems[0].startswith("docs/agent-flow/c.yaml: ")
    assert not (tmp_path / "skills").exists()


def test_build_skills_when_outside(tmp_path: Path, write_flow: Callable[[str, str], Path]) -> None:
    """`skill.path` がリポジトリの外を指す（異常系）。"""
    from rule_inject.features.build_skills.service import build_skills
    from rule_inject.features.build_skills.types import SkillBuildError

    # 準備
    write_flow("a.yaml", FLOW_A.replace("skills/a/SKILL.md", "../x/SKILL.md"))
    # 実行
    with pytest.raises(SkillBuildError) as caught:
        build_skills(tmp_path)
    # 検証
    assert caught.value.problems == ("docs/agent-flow/a.yaml: skill.path",)
    assert not (tmp_path.parent / "x").exists()


def test_render_skill() -> None:
    """frontmatter と本文を約束どおりに組み立てる（正常系）。"""
    from rule_inject.features.build_skills.service import render_skill

    # 準備
    flow = {
        "type": "skill",
        "title": "デモ",
        "summary": LONG_DESCRIPTION,
        "skill": {
            "path": "skills/demo/SKILL.md",
            "arguments": [
                {"name": "index", "hint": "[索引のパス]", "description": "索引のパス"},
            ],
        },
        "steps": [
            {
                "name": "確認する",
                "when": "`$index` を指定したとき",
                "body": "索引を確認する。",
                "calls": [
                    {
                        "type": "mcp",
                        "server": "MCP-122-1#",
                        "tool": "check_indexes",
                        "args": {"required": ["project_dir"]},
                    },
                    {"type": "tool", "tool": "AskUserQuestion"},
                ],
            },
            {"name": "結果を示す", "body": "結果を示す。"},
        ],
        "refs": ["IF-122-21#"],
    }
    # 実行
    result = render_skill("docs/agent-flow/demo.yaml", flow)
    # 検証
    assert result.path == "skills/demo/SKILL.md"
    assert result.content == SKILL_DEMO


def test_render_skill_when_frontmatter() -> None:
    """`skill.frontmatter` を末尾に続け、`skill.arguments` が無ければ `arguments` と引数の表を出さない（正常系）。"""
    from rule_inject.features.build_skills.service import render_skill

    # 準備
    flow = {
        "type": "skill",
        "title": "g",
        "summary": "g のスキル",
        "skill": {
            "path": "skills/g/SKILL.md",
            "frontmatter": {"argument-hint": "[--yes|--no]"},
        },
        "steps": [{"name": "実行する", "body": "`$ARGUMENTS` を確認する。"}],
    }
    # 実行
    result = render_skill("docs/agent-flow/g.yaml", flow)
    # 検証
    assert result.content.startswith(
        "---\nname: g\ndescription: g のスキル\nargument-hint: '[--yes|--no]'\n---\n"
    )
    assert "## 引数" not in result.content


def test_render_skill_when_key_missing() -> None:
    """組み立てに要るキーが無い（異常系）。"""
    from rule_inject.features.build_skills.service import render_skill
    from rule_inject.features.build_skills.types import SkillBuildError

    # 準備
    flow = {
        "type": "skill",
        "title": "x",
        "summary": "x のスキル",
        "skill": {},
        "steps": [{"name": "実行する", "body": "実行する。"}],
    }
    # 実行
    with pytest.raises(SkillBuildError) as caught:
        render_skill("docs/agent-flow/x.yaml", flow)
    # 検証
    assert caught.value.problems == ("docs/agent-flow/x.yaml: skill.path",)
