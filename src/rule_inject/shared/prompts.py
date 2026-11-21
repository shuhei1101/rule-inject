"""フックの注入文のプロンプトファイルを名前で参照し、標準ライブラリだけで描画する。"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from rule_inject.shared.errors import PromptLoadError, describe
from rule_inject.shared.yaml_lines import parse_scalar

# このファイル（src/rule_inject/shared/prompts.py）から導いたプラグインのルート
PLUGIN_ROOT = Path(__file__).resolve().parents[3]
# プラグインのルートからのフックのプロンプトファイルのフォルダ
HOOK_PROMPTS_DIR = Path("content") / "prompts" / "hook" / "rule-inject"
# 本文の `{{ 名前 }}`（名前をグループで取る）
VARIABLE_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")
# 部品の `when` として受け付ける形式（変数の名前 1 つ）
WHEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# `{{ 名前 }}` を除いた後に残っていれば描画できない Jinja2 の構文
UNSUPPORTED_SYNTAX = ("{{", "{%", "{#")
# 本文のブロックスカラーの指示子（`|` は末尾の改行を 1 つ残し、`|-` は残さない）
BLOCK_INDICATORS = ("|", "|-")
LIST_ITEM_PREFIX = "- "

# 要素のキー 1 つを処理し、次の行の位置を返却する（引数はキー・値・次の行の位置・要素のキーの字下げ・要素）
type KeyReader = Callable[[str, str, int, int, dict[str, object]], int]


@dataclass(frozen=True, slots=True, kw_only=True)
class HookPromptPart:
    """部品 1 つの id・条件・言語ごとの本文。"""

    id: str
    # 使用する条件の変数の名前（無ければ None）
    when: str | None
    # 言語 → 本文
    texts: Mapping[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class HookPrompt:
    """プロンプトファイルから取り出した注入する言語と部品の並び。"""

    lang: str
    parts: tuple[HookPromptPart, ...]


def _indent(raw: str) -> int:
    """行頭の空白の数を返却する。"""
    return len(raw) - len(raw.lstrip(" "))


def _is_skippable(raw: str) -> bool:
    """空行かコメントの行かを返却する。"""
    stripped = raw.strip()
    return not stripped or stripped.startswith("#")


def _split_key(text: str, number: int, path: Path) -> tuple[str, str]:
    """`キー: 値` をキーと値に分ける。"""
    key, sep, value = text.strip().partition(":")
    if not sep or not key.strip():
        raise PromptLoadError(str(path), f"{number}行目: キーの行ではありません")
    return key.strip(), value.strip()


def _scalar(value: str, number: int, path: Path) -> str:
    """値を引用符を除いた文字列にする。"""
    try:
        return parse_scalar(value, number)
    except ValueError as exc:
        raise PromptLoadError(str(path), str(exc)) from exc


def _skip_nested(raw: list[str], start: int, indent: int) -> int:
    """`indent` より深い字下げの行（空行・コメントを含む）を飛ばし、次の行の位置を返却する。"""
    index = start
    while index < len(raw) and (_is_skippable(raw[index]) or _indent(raw[index]) > indent):
        index += 1
    return index


def _read_block(raw: list[str], start: int, indent: int, indicator: str) -> tuple[str, int]:
    """`indent` より深い行をブロックスカラーの本文として取り出し、本文と次の行の位置を返却する。"""
    end = start
    while end < len(raw) and (not raw[end].strip() or _indent(raw[end]) > indent):
        end += 1
    lines = raw[start:end]
    # 末尾の空行は本文に含めない
    while lines and not lines[-1].strip():
        lines.pop()
    # 最初の本文の行の字下げを全ての行から除く
    base = _indent(lines[0]) if lines else 0
    body = "\n".join(line[base:] if line.strip() else "" for line in lines)
    # `|` は末尾の改行を 1 つ残す
    if indicator == "|" and body:
        body += "\n"
    return body, end


def _read_list(
    raw: list[str], start: int, parent_indent: int, path: Path, read_key: KeyReader
) -> tuple[list[tuple[int, dict[str, object]]], int]:
    """`parent_indent` より深い `- ` で始まる要素を並び順に取り出し、(行番号, 要素) の並びと次の行の位置を返却する。"""
    items: list[tuple[int, dict[str, object]]] = []
    index = start
    key_indent = parent_indent
    while index < len(raw):
        line = raw[index]
        if _is_skippable(line):
            index += 1
            continue
        if _indent(line) <= parent_indent:
            break
        number = index + 1
        content = line.strip()
        if content.startswith(LIST_ITEM_PREFIX):
            # `- ` の行: 次の要素を始め、`- ` の後ろを要素の最初のキーとして扱う
            key_indent = _indent(line) + len(LIST_ITEM_PREFIX)
            items.append((number, {}))
            content = content[len(LIST_ITEM_PREFIX) :]
        elif not items or _indent(line) != key_indent:
            # 要素の外か、要素のキーと字下げが違う行: 構造が違う
            raise PromptLoadError(str(path), f"{number}行目: 要素の字下げが違います")
        key, value = _split_key(content, number, path)
        index = read_key(key, value, index + 1, key_indent, items[-1][1])
    return items, index


def _read_texts(raw: list[str], start: int, indent: int, path: Path) -> tuple[dict[str, str], int]:
    """部品の `texts` の要素（`lang` と `text`）を取り出し、言語 → 本文と次の行の位置を返却する。"""

    def read_key(key: str, value: str, index: int, key_indent: int, item: dict[str, object]) -> int:
        if key == "lang":
            item["lang"] = _scalar(value, index, path)
            return index
        if key == "text":
            # 本文はブロックスカラーだけを受け付ける
            if value not in BLOCK_INDICATORS:
                raise PromptLoadError(
                    str(path), f"{index}行目: text がブロックスカラーではありません"
                )
            item["text"], next_index = _read_block(raw, index, key_indent, value)
            return next_index
        return _skip_nested(raw, index, key_indent)

    items, end = _read_list(raw, start, indent, path, read_key)
    texts: dict[str, str] = {}
    for number, item in items:
        lang, text = item.get("lang"), item.get("text")
        if not isinstance(lang, str) or not isinstance(text, str):
            raise PromptLoadError(
                str(path), f"{number}行目: texts の要素が lang か text を持ちません"
            )
        texts[lang] = text
    return texts, end


def _read_parts(raw: list[str], start: int, path: Path) -> tuple[list[HookPromptPart], int]:
    """`parts` の下の部品を取り出し、部品の並びと次の行の位置を返却する。"""

    def read_key(key: str, value: str, index: int, key_indent: int, item: dict[str, object]) -> int:
        if key in ("id", "when"):
            item[key] = _scalar(value, index, path)
            return index
        if key == "texts":
            item["texts"], next_index = _read_texts(raw, index, key_indent, path)
            return next_index
        return _skip_nested(raw, index, key_indent)

    items, end = _read_list(raw, start, 0, path, read_key)
    parts: list[HookPromptPart] = []
    for number, item in items:
        part_id, when, texts = item.get("id"), item.get("when"), item.get("texts")
        if not isinstance(part_id, str) or not isinstance(texts, dict):
            raise PromptLoadError(str(path), f"{number}行目: 部品が id か texts を持ちません")
        parts.append(
            HookPromptPart(id=part_id, when=when if isinstance(when, str) else None, texts=texts)
        )
    return parts, end


def _parse_prompt(text: str, path: Path) -> HookPrompt:
    """プロンプトファイルの YAML から、最上位の `lang` と `parts[]` の `id`・`when`・`texts[]` だけを取り出す。"""
    raw = text.splitlines()
    lang: str | None = None
    parts: list[HookPromptPart] | None = None
    index = 0
    while index < len(raw):
        line = raw[index]
        if _is_skippable(line):
            index += 1
            continue
        number = index + 1
        if _indent(line) != 0:
            raise PromptLoadError(str(path), f"{number}行目: 最上位のキーの字下げが違います")
        key, value = _split_key(line, number, path)
        if key == "lang":
            lang = _scalar(value, number, path)
            index += 1
        elif key == "parts":
            parts, index = _read_parts(raw, index + 1, path)
        else:
            # lang・parts 以外の最上位のキーは、その下の行ごと飛ばす
            index = _skip_nested(raw, index + 1, 0)
    if lang is None or parts is None:
        raise PromptLoadError(str(path), f"{len(raw)}行目までに最上位の lang か parts がありません")
    return HookPrompt(lang=lang, parts=tuple(parts))


@cache
def _load_prompt(path: Path) -> HookPrompt:
    """プロンプトファイルを取り出す（同じプロセスで同じファイルを 2 回参照しない。例外はキャッシュされない）。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptLoadError(str(path), describe(exc)) from exc
    return _parse_prompt(text, path)


def _render_text(template: str, values: Mapping[str, object], part_id: str, path: Path) -> str:
    """本文の `{{ 名前 }}` を値で置き換える。"""
    if any(syntax in VARIABLE_PATTERN.sub("", template) for syntax in UNSUPPORTED_SYNTAX):
        raise PromptLoadError(str(path), f"部品 {part_id} に置き換えられない構文があります")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise PromptLoadError(str(path), f"部品 {part_id} の変数 {name} がありません")
        return str(values[name])

    return VARIABLE_PATTERN.sub(replace, template)


def load_hook_prompt(
    name: str, values: Mapping[str, object] | None = None, *, root: Path = PLUGIN_ROOT
) -> str:
    """名前のプロンプトファイルを参照し、`when` が真の部品の本文を値で置き換えてつないだ文を返却する。"""
    path = root / HOOK_PROMPTS_DIR / f"{name}.yaml"
    prompt = _load_prompt(path)
    given: Mapping[str, object] = values or {}
    rendered: list[str] = []
    for part in prompt.parts:
        # 条件を持つ部品は、変数の値が偽なら飛ばす
        if part.when is not None:
            if not WHEN_PATTERN.fullmatch(part.when):
                raise PromptLoadError(
                    str(path), f"部品 {part.id} の when は変数の名前 1 つにします"
                )
            if part.when not in given:
                raise PromptLoadError(str(path), f"部品 {part.id} の変数 {part.when} がありません")
            if not given[part.when]:
                continue
        template = part.texts.get(prompt.lang)
        if template is None:
            raise PromptLoadError(str(path), f"部品 {part.id} に {prompt.lang} の本文がありません")
        rendered.append(_render_text(template, given, part.id, path))
    return "".join(rendered).rstrip("\n")
