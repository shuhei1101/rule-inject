"""Bash のコマンドの文字列から、読むコマンドが読むファイルの絶対パスを取り出す。"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

# ルール案内が読む操作として扱うコマンド
READ_COMMANDS = frozenset(
    {"cat", "head", "tail", "less", "more", "grep", "rg", "sed", "awk", "wc", "bat"}
)
# 既読の記録が既読にするコマンド（本文全体を出すもの）
FULL_READ_COMMANDS = frozenset({"cat", "bat", "less", "more"})

CD_COMMAND = "cd"
# コマンドの区切り（`&&` `||` `;` `|` とリダイレクトなど、記号だけでできた語）
PUNCTUATION_CHARS = "();<>|&"


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
