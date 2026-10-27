"""Bash のコマンドの文字列から、読むコマンドが読むファイルの絶対パスを取り出し、検索のコマンドとその結果の行から実在するファイルを拾う。"""

from __future__ import annotations

import glob
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
NEWLINE = "\n"
# コマンドの区切り（`&&` `||` `;` `|` と改行、リダイレクトなど、記号だけでできた語）
PUNCTUATION_CHARS = "();<>|&\n"
# 語を分ける空白（改行はコマンドの区切りにするため含めない）
WHITESPACE_CHARS = " \t\r"
# パターンとして展開する文字
GLOB_CHARS = frozenset("*?[")
QUOTE_CHARS = frozenset("'\"")
DOUBLE_QUOTE = '"'
ESCAPE_CHAR = "\\"
# 二重引用符の中で、直後の文字をエスケープする文字
DOUBLE_QUOTE_ESCAPED = frozenset('"\\')
COMMENT_CHAR = "#"
# コメントの始まりになる、直前の文字
COMMENT_PRECEDERS = frozenset(" \t\r\n;&|()<>")
HEREDOC_OPERATOR = "<<"
FOR_COMMAND = "for"
FOR_IN = "in"
# `for` と同じく本体を `do` と `done` で囲むループ
LOOP_COMMANDS = frozenset({"while", "until"})
DO_COMMAND = "do"
DONE_COMMAND = "done"
OPTION_PREFIX = "-"

# ループの変数と語の並び（変数を持たないループの変数は空）
type Loop = tuple[str, list[str]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultPaths:
    """検索の結果から拾ったパス。"""

    # 照合する実在するファイルの絶対パス（出た順、重なりなし、`limit` 件まで）
    paths: tuple[str, ...]
    # 上限を超えて照合しない実在するファイルの件数
    unchecked: int


def _protect_literals(command: str) -> str:
    """行継続とコメントを除き、引用符の中と `\\` の直後の glob の文字を文字どおりに扱うようにする。"""
    protected: list[str] = []
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        following = command[index + 1 : index + 2]
        # 進める文字数の既定は 1 文字
        step = 1
        if quote:
            # 引用符の中: 閉じる引用符、二重引用符の中のエスケープ、glob の文字の順に見る
            if char == quote:
                quote = ""
                protected.append(char)
            elif (
                quote == DOUBLE_QUOTE and char == ESCAPE_CHAR and following in DOUBLE_QUOTE_ESCAPED
            ):
                protected.append(char + following)
                step = 2
            elif char in GLOB_CHARS:
                protected.append(f"[{char}]")
            else:
                protected.append(char)
        elif char == ESCAPE_CHAR:
            # 引用符の外のエスケープ: 行継続は空白、glob の文字は文字どおり、他はそのまま
            if following == NEWLINE:
                protected.append(" ")
            elif following in GLOB_CHARS:
                protected.append(f"[{following}]")
            else:
                protected.append(char + following)
            step = 2
        elif char in QUOTE_CHARS:
            quote = char
            protected.append(char)
        elif char == COMMENT_CHAR and (index == 0 or command[index - 1] in COMMENT_PRECEDERS):
            # コメントは行末まで捨てる（改行は残す）
            end = command.find(NEWLINE, index)
            step = (end if end >= 0 else len(command)) - index
        else:
            protected.append(char)
        index += step
    return "".join(protected)


def _split_words(command: str) -> list[str] | None:
    """コマンドを語に分ける。引用符が閉じていないなど、分けられなければ None を返す。"""
    lexer = shlex.shlex(_protect_literals(command), posix=True, punctuation_chars=PUNCTUATION_CHARS)
    lexer.whitespace = WHITESPACE_CHARS
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _drop_heredocs(words: list[str]) -> list[str]:
    """ヒアドキュメントの終わりの語と、次の行からの本文の語を捨てる。"""
    kept: list[str] = []
    # 宣言されたが、本文がまだ始まっていない終わりの語
    pending: list[str] = []
    # 本文を捨てている間の、終わりの語と今の行の語
    terminator = ""
    line: list[str] = []
    iterator = iter(words)
    for word in iterator:
        if terminator:
            # 本文: 終わりの語だけの行で終える
            if NEWLINE not in word:
                line.append(word)
            else:
                finished = line == [terminator]
                line = []
                if finished:
                    terminator = pending.pop(0) if pending else ""
            continue
        kept.append(word)
        if word == HEREDOC_OPERATOR:
            # `<<-` の `-` は終わりの語に含めない
            pending.append(next(iterator, "").lstrip(OPTION_PREFIX))
        elif NEWLINE in word and pending:
            # 宣言した行が終わったので、次の行から本文を捨てる
            terminator = pending.pop(0)
    return kept


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


def _command_segments(command: str) -> list[list[str]] | None:
    """コマンドを区切ったコマンドごとの語にする。分けられなければ None を返す。"""
    words = _split_words(command)
    if words is None:
        return None
    return _split_segments(_drop_heredocs(words))


def _resolve(argument: str, base: str) -> str:
    """引数を `~` の展開と基準からの解決で絶対パスにする。"""
    expanded = os.path.expanduser(argument)
    return os.path.normpath(os.path.join(base, expanded))


def _resolve_folder(argument: str, base: str) -> str | None:
    """フォルダの引数を絶対パスにする。glob の文字を含むときは、当たったフォルダが 1 つのときだけ返す。"""
    paths = _expand_word(argument, base)
    if GLOB_CHARS.isdisjoint(argument):
        return paths[0]
    folders = [path for path in paths if os.path.isdir(path)]
    return folders[0] if len(folders) == 1 else None


def _moved_base(segment: list[str], base: str) -> str:
    """`cd {フォルダ}` の区切りで動かした後の基準を返す。"""
    if len(segment) > 1 and not segment[1].startswith(OPTION_PREFIX):
        return _resolve_folder(segment[1], base) or base
    return base


def _start_loop(segment: list[str]) -> Loop:
    """ループの始まりの区切りから、`for` の変数と語の並びを取り出す（取り出せなければ変数なし）。"""
    if segment[0] == FOR_COMMAND and segment[2:3] == [FOR_IN]:
        return segment[1], segment[3:]
    return "", []


def _loop_words(argument: str, loops: list[Loop]) -> list[str]:
    """引数が `for` の変数なら語の並びを、そうでなければ引数そのものを返す。"""
    for variable, words in reversed(loops):
        if variable and argument in (f"${variable}", f"${{{variable}}}"):
            return words
    return [argument]


def _expand_word(word: str, base: str) -> list[str]:
    """語を基準から解いた絶対パスにする。glob の文字を含む語は展開して名前の順に並べる。"""
    if GLOB_CHARS.isdisjoint(word):
        return [_resolve(word, base)]
    matches = sorted(glob.glob(os.path.expanduser(word), root_dir=base))
    return [os.path.normpath(os.path.join(base, match)) for match in matches]


def _argument_paths(segment: list[str], base: str, loops: list[Loop]) -> list[str]:
    """読むコマンドの引数を、`for` の語の並びと glob を展開した絶対パスにする。"""
    paths: list[str] = []
    for argument in segment[1:]:
        for word in _loop_words(argument, loops):
            # オプションは読む対象にしない
            if not word.startswith(OPTION_PREFIX):
                paths.extend(_expand_word(word, base))
    return paths


def extract_read_paths(command: str, cwd: Path, commands: frozenset[str]) -> list[str]:
    """コマンドの文字列から、指定のコマンドが読む実在するファイルの絶対パスを返す。"""
    segments = _command_segments(command)
    if segments is None:
        return []
    base = str(cwd)
    loops: list[Loop] = []
    found: list[str] = []
    for segment in segments:
        # `do` の残りを 1 つのコマンドとして見る
        if segment[0] == DO_COMMAND:
            segment = segment[1:]
            if not segment:
                continue
        head = segment[0]
        # ループの始まりは変数と語の並びを積み、終わりで降ろす
        if head == FOR_COMMAND or head in LOOP_COMMANDS:
            loops.append(_start_loop(segment))
            continue
        if head == DONE_COMMAND:
            if loops:
                loops.pop()
            continue
        name = os.path.basename(head)
        # cd は以降のコマンドの相対パスの基準を動かす
        if name == CD_COMMAND:
            base = _moved_base(segment, base)
            continue
        # 対象のコマンドは、実在するファイルだけを出てきた順に重なりなしで残す
        if name in commands:
            for path in _argument_paths(segment, base, loops):
                if os.path.isfile(path) and path not in found:
                    found.append(path)
    return found


def search_output_base(command: str, cwd: Path) -> Path | None:
    """コマンドが検索のコマンドなら、その出力の相対パスを解くフォルダを返す（検索でなければ None）。"""
    segments = _command_segments(command)
    if segments is None:
        return None
    base = str(cwd)
    for segment in segments:
        name = os.path.basename(segment[0])
        # cd は以降のコマンドの出力の基準を動かす
        if name == CD_COMMAND:
            base = _moved_base(segment, base)
            continue
        # cd を除いた最初のコマンドだけを見る（名前の部分一致にしない）
        if name not in SEARCH_COMMANDS:
            return None
        # ls は、`-` で始まらない引数が実在するフォルダ 1 つだけなら、そのフォルダの名前が出力される
        if name == LIST_COMMAND:
            arguments = [
                argument for argument in segment[1:] if not argument.startswith(OPTION_PREFIX)
            ]
            if len(arguments) == 1:
                folder = _resolve_folder(arguments[0], base)
                if folder is not None and os.path.isdir(folder):
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
