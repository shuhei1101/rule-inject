"""server/prompts.py の単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_prompt(clone: Path, prompt_id: str, text: str) -> Path:
    """クローンの代わりのフォルダの `content/prompts` へプロンプトファイルを配置する。"""
    path = clone / "content" / "prompts" / f"{prompt_id}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_load_prompt(tmp_path: Path) -> None:
    """`when` が真の部品の本文を変数で描画してつなぐ（正常系）。"""
    from rule_inject.server.prompts import load_prompt

    # 準備
    _write_prompt(
        tmp_path,
        "a/b",
        """id: a/b
name: 例
description: 例のプロンプト
kind: tool
lang: ja
vars:
  name:
    type: string
    description: 名前
    example: x
parts:
  - id: always
    texts:
      - lang: ja
        text: |
          {{ name }} さん
  - id: matched
    when: "name == 'x'"
    texts:
      - lang: ja
        text: |
          一致した
  - id: skipped
    when: "false"
    texts:
      - lang: ja
        text: |
          出ない
""",
    )
    # 実行
    result = load_prompt(tmp_path, "a/b", values={"name": "x"})
    # 検証
    assert result == "x さん\n一致した"


def test_load_prompt_when_missing(tmp_path: Path) -> None:
    """ファイルが無ければ読み込みの失敗にする（異常系）。"""
    from rule_inject.server.prompts import PromptLoadError, load_prompt

    # 実行・検証
    with pytest.raises(PromptLoadError) as raised:
        load_prompt(tmp_path, "a/missing")
    assert raised.value.path == tmp_path / "content" / "prompts" / "a" / "missing.yaml"


def test_load_prompt_when_invalid_yaml(tmp_path: Path) -> None:
    """YAML の誤りは読み込みの失敗にする（異常系）。"""
    from rule_inject.server.prompts import PromptLoadError, load_prompt

    # 準備
    path = _write_prompt(tmp_path, "a/broken", "lang: ja\nparts: [\n")
    # 実行・検証
    with pytest.raises(PromptLoadError) as raised:
        load_prompt(tmp_path, "a/broken")
    assert raised.value.path == path


def test_load_prompt_when_no_lang_text(tmp_path: Path) -> None:
    """注入する言語の本文が無い部品があれば読み込みの失敗にする（異常系）。"""
    from rule_inject.server.prompts import PromptLoadError, load_prompt

    # 準備
    _write_prompt(
        tmp_path,
        "a/english",
        """lang: ja
parts:
  - id: only-en
    texts:
      - lang: en
        text: hello
""",
    )
    # 実行・検証
    with pytest.raises(PromptLoadError) as raised:
        load_prompt(tmp_path, "a/english")
    assert "only-en" in raised.value.reason


@pytest.mark.parametrize(
    "part",
    [
        "  - id: body\n    texts:\n      - lang: ja\n        text: '{{ missing }}'\n",
        "  - id: cond\n    when: missing\n    texts:\n      - lang: ja\n        text: x\n",
    ],
    ids=["本文", "when"],
)
def test_load_prompt_when_undefined(tmp_path: Path, part: str) -> None:
    """`vars` に無い変数は描画の失敗にする（異常系）。"""
    from rule_inject.server.prompts import PromptLoadError, load_prompt

    # 準備
    _write_prompt(tmp_path, "a/undefined", "lang: ja\nparts:\n" + part)
    # 実行・検証
    with pytest.raises(PromptLoadError):
        load_prompt(tmp_path, "a/undefined")
