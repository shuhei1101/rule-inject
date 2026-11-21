"""インターフェース定義『SKILL.md の生成』の結合テスト。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

TIMEOUT_SEC = 30

FLOW_A = """\
type: skill
title: a のスキル
summary: a の索引を登録し、チェックの結果を示す
skill:
  path: skills/a/SKILL.md
  arguments:
    - name: index
      hint: '[索引のパス]'
      description: 索引のパス
steps:
  - name: 索引を登録する
    when: '`$index` を指定したとき'
    body: '- 端末の設定に索引を追加する'
    calls:
      - type: mcp
        server: MCP-122-1#
        tool: check_indexes
        args:
          required:
            - project_dir
      - type: tool
        tool: AskUserQuestion
  - name: 結果を示す
    body: '- チェックの結果を示す'
refs:
  - IF-122-21#
"""

SKILL_A = """\
---
name: a
description: a の索引を登録し、チェックの結果を示す
argument-hint: '[索引のパス]'
arguments:
- index
---

<!-- docs/agent-flow/a.yaml から生成した。このファイルを修正せず、設計書を修正して再生成する -->

# a のスキル

## 引数

| 引数 | 説明 |
| --- | --- |
| `$index` | 索引のパス |

## 手順

### 索引を登録する

`$index` を指定したときだけ行う。

- 端末の設定に索引を追加する

呼ぶもの:
- MCP `MCP-122-1#` の `check_indexes` `{required: [project_dir]}`
- ツール `AskUserQuestion`

### 結果を示す

- チェックの結果を示す
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
type: flow
title: c
summary: c の流れ
skill:
  path: skills/c/SKILL.md
steps:
  - name: 実行する
    body: c を実行する。
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """正常系の一時フォルダ（`a.yaml`・`b.yaml`・`c.yaml` と、生成済みの `b` の SKILL.md）。"""
    flow_dir = tmp_path / "docs" / "agent-flow"
    flow_dir.mkdir(parents=True)
    (flow_dir / "a.yaml").write_text(FLOW_A, encoding="utf-8")
    (flow_dir / "b.yaml").write_text(FLOW_B, encoding="utf-8")
    (flow_dir / "c.yaml").write_text(FLOW_C, encoding="utf-8")
    skill_b = tmp_path / "skills" / "b" / "SKILL.md"
    skill_b.parent.mkdir(parents=True)
    skill_b.write_bytes(SKILL_B.encode("utf-8"))
    return tmp_path


@pytest.fixture
def run_build(repo: Path) -> Callable[[], subprocess.CompletedProcess[str]]:
    """リポジトリの直下で `python -m rule_inject.build_skills` を子プロセスで実行する関数。"""

    def _run() -> subprocess.CompletedProcess[str]:
        """一時フォルダを作業ディレクトリにして実行し、結果を返却する。"""
        return subprocess.run(
            [sys.executable, "-m", "rule_inject.build_skills"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            check=False,
        )

    return _run


def test_normal(repo: Path, run_build: Callable[[], subprocess.CompletedProcess[str]]) -> None:
    """組み立てた中身が今の SKILL.md と違うエージェントフローだけ、SKILL.md を書き出す（正常系）。"""
    # 準備
    skill_a = repo / "skills" / "a" / "SKILL.md"
    skill_b = repo / "skills" / "b" / "SKILL.md"
    # 実行
    first = run_build()
    second = run_build()
    # 検証
    assert first.returncode == 0
    assert first.stdout == "skills/a/SKILL.md\n"
    assert skill_a.read_bytes() == SKILL_A.encode("utf-8")
    assert skill_b.read_bytes() == SKILL_B.encode("utf-8")
    assert not (repo / "skills" / "c").exists()
    assert second.returncode == 0
    assert second.stdout == ""
    assert skill_a.read_bytes() == SKILL_A.encode("utf-8")
    assert skill_b.read_bytes() == SKILL_B.encode("utf-8")


def test_error_when_flow_unreadable(
    repo: Path, run_build: Callable[[], subprocess.CompletedProcess[str]]
) -> None:
    """YAML として読み込めないエージェントフローがあれば、どの SKILL.md も書き換えずに終わる（異常系）。"""
    # 準備
    (repo / "docs" / "agent-flow" / "c.yaml").write_text('title: "c\n', encoding="utf-8")
    # 実行
    result = run_build()
    # 検証
    assert result.returncode == 2
    assert "docs/agent-flow/c.yaml" in result.stderr
    assert not (repo / "skills" / "a").exists()
    assert (repo / "skills" / "b" / "SKILL.md").read_bytes() == SKILL_B.encode("utf-8")


def test_error_when_key_missing(
    repo: Path, run_build: Callable[[], subprocess.CompletedProcess[str]]
) -> None:
    """組み立てに要るキーが無いエージェントフローがあれば、どの SKILL.md も書き換えずに終わる（異常系）。"""
    # 準備
    (repo / "docs" / "agent-flow" / "b.yaml").write_text(
        FLOW_B.replace("  path: skills/b/SKILL.md\n", ""), encoding="utf-8"
    )
    # 実行
    result = run_build()
    # 検証
    assert result.returncode == 2
    assert "docs/agent-flow/b.yaml: skill.path" in result.stderr
    assert not (repo / "skills" / "a").exists()
    assert (repo / "skills" / "b" / "SKILL.md").read_bytes() == SKILL_B.encode("utf-8")
