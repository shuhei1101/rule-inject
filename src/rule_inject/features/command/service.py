"""Bash のコマンドの文字列から、読むコマンドが読むファイルの絶対パスを取り出し、検索のコマンドとその結果の行から実在するファイルを拾う。"""

from __future__ import annotations

import os
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# ルール案内が読む操作として扱うコマンド
READ_COMMANDS = frozenset(
    {"cat", "head", "tail", "less", "more", "grep", "rg", "sed", "awk", "wc", "bat"}
)
# 既読の記録が既読にするコマンド（本文全体を出すもの）
FULL_READ_COMMANDS = frozenset({"cat", "bat", "less", "more"})
# 検索結果の案内が結果を読むコマンド
SEARCH_COMMANDS = frozenset({"grep", "rg", "find", "ls"})
# 検索の結果から拾って照合するパスの上限
SEARCH_PATH_LIMIT = 100

CD_COMMAND = "cd"
LIST_COMMAND = "ls"
RESULT_LINE_SEPARATOR = ":"
# コマンドの区切り（`&&` `||` `;` `|` とリダイレクトなど、記号だけでできた語）
PUNCTUATION_CHARS = "();<>|&"


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultPaths:
    """検索の結果から拾ったパス。"""

    # 照合する実在するファイルの絶対パス（出た順、重なりなし、`limit` 件まで）
    paths: tuple[str, ...]
    # 上限を超えて照合しない実在するファイルの件数
    unchecked: int


def _split_words(command: str) -> list[str] | None:
    """コマンドを語に分ける。引用符が閉じていないなど、分けられなければ None を返す。"""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _split_segments(words: list[str]) -> list[list[str]]:
    """記号だけの語でコマンドごとに区切る。"""
    segments: list[list[str]] = [[]]
    for word in words:
        # 記号だけの語は次のコマンドの始まり
        if set(word) <= set(PUNCTUATION_CHARS):
            segments.append([])
        else:
            segments[-1].append(word)
    return [segment for segment in segments if segment]


def _resolve(argument: str, base: str) -> str:
    """引数を `~` の展開と基準からの解決で絶対パスにする。"""
    expanded = os.path.expanduser(argument)
    return os.path.normpath(os.path.join(base, expanded))


def extract_read_paths(command: str, cwd: Path, commands: frozenset[str]) -> list[str]:
    """コマンドの文字列から、指定のコマンドが読む実在するファイルの絶対パスを返す。"""
    words = _split_words(command)
    if words is None:
        return []
    base = str(cwd)
    found: list[str] = []
    for segment in _split_segments(words):
        name = os.path.basename(segment[0])
        # cd は以降のコマンドの相対パスの基準を動かす
        if name == CD_COMMAND:
            if len(segment) > 1 and not segment[1].startswith("-"):
                base = _resolve(segment[1], base)
            continue
        # 対象のコマンドは、`-` で始まらない引数のうち実在するファイルだけを残す
        if name in commands:
            for argument in segment[1:]:
                if argument.startswith("-"):
                    continue
                resolved = _resolve(argument, base)
                if os.path.isfile(resolved) and resolved not in found:
                    found.append(resolved)
    return found


def search_output_base(command: str, cwd: Path) -> Path | None:
    """コマンドが検索のコマンドなら、その出力の相対パスを解くフォルダを返す（検索でなければ None）。"""
    words = _split_words(command)
    if words is None:
        return None
    base = str(cwd)
    for segment in _split_segments(words):
        name = os.path.basename(segment[0])
        # cd は以降のコマンドの出力の基準を動かす
        if name == CD_COMMAND:
            if len(segment) > 1 and not segment[1].startswith("-"):
                base = _resolve(segment[1], base)
            continue
        # cd を除いた最初のコマンドだけを見る（名前の部分一致にしない）
        if name not in SEARCH_COMMANDS:
            return None
        # ls は、`-` で始まらない引数が実在するフォルダ 1 つだけなら、そのフォルダの名前が出力される
        if name == LIST_COMMAND:
            arguments = [argument for argument in segment[1:] if not argument.startswith("-")]
            if len(arguments) == 1:
                folder = _resolve(arguments[0], base)
                if os.path.isdir(folder):
                    base = folder
        return Path(base)
    return None


def _result_path(line: str, base: Path) -> str | None:
    """結果の 1 行から実在するファイルの絶対パスを拾う（拾えなければ None）。"""
    stripped = line.strip()
    if not stripped:
        return None
    # 行全体がファイルを指せばそのパス（名前に `:` を含むファイルも拾う）
    whole = _resolve(stripped, str(base))
    if os.path.isfile(whole):
        return whole
    # そうでなければ最初の `:` より前（`{パス}:{行番号}:{行}` と `{パス}:{件数}`）
    head = stripped.split(RESULT_LINE_SEPARATOR, 1)[0]
    if head and head != stripped:
        resolved = _resolve(head, str(base))
        if os.path.isfile(resolved):
            return resolved
    return None


def extract_result_paths(
    lines: Iterable[str], base: Path, *, limit: int = SEARCH_PATH_LIMIT
) -> ResultPaths:
    """検索の結果の行から実在するファイルの絶対パスを拾い、上限までを照合するパスにする。"""
    found = [_result_path(line, base) for line in lines]
    # 拾えなかった行を除き、重なりを落として出た順に並べる
    unique = list(dict.fromkeys(path for path in found if path is not None))
    return ResultPaths(paths=tuple(unique[:limit]), unchecked=max(len(unique) - limit, 0))
