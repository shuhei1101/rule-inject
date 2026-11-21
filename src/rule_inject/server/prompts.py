"""クローンのプロンプトファイルを id で読み込み、注入する言語の本文を描画する。"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

# クローンの直下からのプロンプトファイルのフォルダ
PROMPTS_DIR = Path("content") / "prompts"
# 部品の本文と when を描画・評価する設定（project-index の描画とそろえる）
ENVIRONMENT = Environment(
    undefined=StrictUndefined,
    autoescape=False,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


class PromptLoadError(Exception):
    """プロンプトファイルが無い・読めない・描画できない。"""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def load_prompt(clone: Path, prompt_id: str, *, values: Mapping[str, object] | None = None) -> str:
    """id のプロンプトファイルを読み込み、`when` が真の部品の `lang` の本文を描画してつないだ文を返却する。"""
    path = clone / PROMPTS_DIR / f"{prompt_id}.yaml"
    # ファイルを読み、YAML として読み込む
    try:
        document: Any = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise PromptLoadError(path, f"読めない: {exc}") from exc
    # 最上位が lang（文字列）と parts（配列）を持つ辞書か
    if (
        not isinstance(document, dict)
        or not isinstance(document.get("lang"), str)
        or not isinstance(document.get("parts"), list)
    ):
        raise PromptLoadError(path, "最上位に lang（文字列）と parts（配列）がありません")
    lang: str = document["lang"]
    # 指定されなかった変数は None にする（vars の名前だけを埋め、vars に無い変数は未定義のまま）
    variables: dict[str, object] = dict.fromkeys(document.get("vars") or {})
    variables.update(values or {})
    rendered: list[str] = []
    for part in document["parts"]:
        part_id = part.get("id")
        try:
            when = part.get("when")
            # when があり偽: この部品を使わない（未定義の変数は None にせず例外にする）
            if when is not None and not bool(
                ENVIRONMENT.compile_expression(str(when), undefined_to_none=False)(**variables)
            ):
                continue
            texts = [item["text"] for item in part.get("texts") or [] if item.get("lang") == lang]
            # 注入する言語の本文が無い: 読み込みの失敗
            if not texts:
                raise PromptLoadError(path, f"部品 {part_id} に {lang} の本文がありません")
            rendered.append(ENVIRONMENT.from_string(texts[0]).render(**variables))
        except TemplateError as exc:
            raise PromptLoadError(path, f"部品 {part_id} を描画できません: {exc}") from exc
    return "".join(rendered).rstrip("\n")
