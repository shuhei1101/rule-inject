"""SKILL.md の生成で組み立てたファイルと、生成を止める誤りの型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class BuiltSkill:
    """1 つの `type: skill` のエージェントフローから組み立てた SKILL.md。"""

    # 書き出す先のリポジトリの直下からのパス（`skill.path`）
    path: str
    # 組み立てた SKILL.md の中身（末尾を改行 1 つで終える）
    content: str


class SkillBuildError(Exception):
    """エージェントフローが読み込めない・組み立てに要るキーが無い・`skill.path` がリポジトリの外を指す。"""

    def __init__(self, problems: tuple[str, ...]) -> None:
        """`{エージェントフローのパス}: {項目か理由}` の並びを持つ。"""
        super().__init__("\n".join(problems))
        self.problems = problems
