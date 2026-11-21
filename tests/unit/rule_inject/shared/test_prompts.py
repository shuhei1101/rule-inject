"""shared/prompts.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from rule_inject.shared import prompts
from rule_inject.shared.errors import PromptLoadError
from rule_inject.shared.prompts import (
    HOOK_PROMPTS_DIR,
    PLUGIN_ROOT,
    _parse_prompt,
    load_hook_prompt,
)

# 部品 1 つの本文が `{text}` で、`when` が `{when}` のプロンプトファイル
PART_PROMPT = "lang: ja\nparts:\n  - id: a\n{when}    texts:\n      - lang: ja\n        text: |-\n          {text}\n"


@pytest.fixture
def write_prompt(tmp_path: Path) -> Callable[[str, str], Path]:
    """一時フォルダのフックのプロンプトファイルのフォルダに、名前と中身のファイルを配置する。"""

    def write(name: str, content: str) -> Path:
        folder = tmp_path / HOOK_PROMPTS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.yaml"
        path.write_text(content, encoding="utf-8")
        return path

    return write


def _part_prompt(text: str, when: str | None = None) -> str:
    """部品 1 つのプロンプトファイルの中身を作る。"""
    when_line = f"    when: {when}\n" if when is not None else ""
    return PART_PROMPT.format(when=when_line, text=text)


def test_load_hook_prompt(tmp_path: Path, write_prompt: Callable[[str, str], Path]) -> None:
    """`when` が真の部品の本文を変数で置き換えてつなぐ（正常系）。"""
    # 準備
    write_prompt(
        "a",
        "lang: ja\n"
        "parts:\n"
        "  - id: body\n"
        "    texts:\n"
        "      - lang: ja\n"
        "        text: |-\n"
        "          {{ name }} さん\n"
        "  - id: flag\n"
        "    when: flag\n"
        "    texts:\n"
        "      - lang: ja\n"
        "        text: |-\n"
        "          ！\n"
        "  - id: off\n"
        "    when: off\n"
        "    texts:\n"
        "      - lang: ja\n"
        "        text: |-\n"
        "          ？\n",
    )
    # 実行
    result = load_hook_prompt("a", {"name": "x", "flag": True, "off": ""}, root=tmp_path)
    # 検証
    assert result == "x さん！"


def test_load_hook_prompt_when_missing(tmp_path: Path) -> None:
    """ファイルが無ければ読み込みの失敗にする（異常系）。"""
    # 実行・検証
    with pytest.raises(PromptLoadError) as caught:
        load_hook_prompt("missing", root=tmp_path)
    assert caught.value.path == str(tmp_path / HOOK_PROMPTS_DIR / "missing.yaml")


def test_load_hook_prompt_when_no_lang_text(
    tmp_path: Path, write_prompt: Callable[[str, str], Path]
) -> None:
    """注入する言語の本文が無い部品があれば読み込みの失敗にする（異常系）。"""
    # 準備
    write_prompt(
        "en-only",
        "lang: ja\nparts:\n  - id: english\n    texts:\n      - lang: en\n        text: |-\n          hello\n",
    )
    # 実行・検証
    with pytest.raises(PromptLoadError) as caught:
        load_hook_prompt("en-only", root=tmp_path)
    assert "english" in caught.value.reason


def test_load_hook_prompt_when_undefined(
    tmp_path: Path, write_prompt: Callable[[str, str], Path]
) -> None:
    """`values` に無い変数は描画の失敗にする（異常系）。"""
    # 準備
    write_prompt("text-var", _part_prompt("{{ missing }}"))
    write_prompt("when-var", _part_prompt("a", when="missing"))
    # 実行・検証
    with pytest.raises(PromptLoadError):
        load_hook_prompt("text-var", root=tmp_path)
    with pytest.raises(PromptLoadError):
        load_hook_prompt("when-var", root=tmp_path)


def test_load_hook_prompt_when_unsupported_syntax(
    tmp_path: Path, write_prompt: Callable[[str, str], Path]
) -> None:
    """置き換えられない Jinja2 の構文は描画の失敗にする（異常系）。"""
    # 準備
    write_prompt("block", _part_prompt("{% if x %}a{% endif %}"))
    write_prompt("expression", _part_prompt("a", when='"x == 1"'))
    # 実行・検証
    with pytest.raises(PromptLoadError):
        load_hook_prompt("block", {"x": 1}, root=tmp_path)
    with pytest.raises(PromptLoadError):
        load_hook_prompt("expression", {"x": 1}, root=tmp_path)


def test_hook_prompts_render() -> None:
    """配布するフックのプロンプトファイルを全て描画できる（正常系）。"""
    # 準備
    files = sorted((PLUGIN_ROOT / HOOK_PROMPTS_DIR).glob("*.yaml"))
    yaml = YAML(typ="safe")
    # 実行・検証
    assert files
    for path in files:
        variables = yaml.load(path.read_text(encoding="utf-8")).get("vars") or {}
        values = {name: spec.get("example", "") for name, spec in variables.items()}
        load_hook_prompt(path.stem, values)


def test_load_hook_prompt_when_read_twice(
    tmp_path: Path,
    write_prompt: Callable[[str, str], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同じファイルを 2 回読まない（正常系）。"""
    # 準備
    write_prompt("twice", _part_prompt("{{ name }}"))
    calls: list[Path] = []
    original = Path.read_text

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        calls.append(self)
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    # 実行
    first = load_hook_prompt("twice", {"name": "a"}, root=tmp_path)
    second = load_hook_prompt("twice", {"name": "b"}, root=tmp_path)
    # 検証
    assert (first, second) == ("a", "b")
    assert len(calls) == 1


def test_parse_prompt() -> None:
    """`lang` と部品を取り出し、ほかの最上位のキーを読み飛ばす（正常系）。"""
    # 準備
    text = (
        "# yaml-language-server: $schema=https://example.com/prompt.schema.yaml\n"
        "id: hook/x\n"
        "vars:\n"
        "  name:\n"
        "    type: string\n"
        "    example: 'a'\n"
        "tags:\n"
        "  - topic:フック\n"
        "lang: ja\n"
        "parts:\n"
        "  - id: first\n"
        "    texts:\n"
        "      - lang: ja\n"
        "        text: |-\n"
        "          1 行目\n"
        "          2 行目\n"
        "  - id: second\n"
        "    when: name\n"
        "    texts:\n"
        "      - lang: ja\n"
        "        text: |-\n"
        "          {{ name }}\n"
    )
    # 実行
    result = _parse_prompt(text, Path("/p/x.yaml"))
    # 検証
    assert result.lang == "ja"
    assert [part.id for part in result.parts] == ["first", "second"]
    assert result.parts[0].when is None
    assert result.parts[1].when == "name"
    assert result.parts[0].texts["ja"] == "1 行目\n2 行目"


def test_parse_prompt_when_invalid() -> None:
    """構造が違えば読み取りの失敗にする（異常系）。"""
    # 準備
    no_parts = "lang: ja\n"
    not_block = "lang: ja\nparts:\n  - id: a\n    texts:\n      - lang: ja\n        text: a\n"
    # 実行・検証
    with pytest.raises(PromptLoadError) as missing:
        _parse_prompt(no_parts, Path("/p/a.yaml"))
    with pytest.raises(PromptLoadError) as scalar:
        _parse_prompt(not_block, Path("/p/b.yaml"))
    assert "行" in missing.value.reason
    assert "6" in scalar.value.reason
