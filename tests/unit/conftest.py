"""単体テストが共有する fixture。"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest

SESSION_ID = "2f9c1b7e-0d54-4b7a-9d4f-5c3a1e2b7f10"
SECONDS_PER_DAY = 86_400
# 掃除の単体テストが固定する現在の時刻（UNIX 時刻の秒）
FIXED_NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """実際のホームの既定の索引（`~/.config/rule-inject/rules.yaml`）を読まないよう HOME を一時フォルダへ向ける。"""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def session_id() -> str:
    """テストで使うセッションの識別子。"""
    return SESSION_ID


@pytest.fixture
def now() -> Callable[[], float]:
    """固定した現在の時刻（UNIX 時刻の秒）を返す関数。"""
    return lambda: FIXED_NOW


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """既読の記録とログを置く記録フォルダ（まだ作らない）。"""
    return tmp_path / "state"


@pytest.fixture
def log_folder(tmp_path: Path) -> Path:
    """日付ごとのログを置くログのフォルダ（まだ作らない）。"""
    return tmp_path / "logs"


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Path]:
    """設定ファイルの YAML を書き、そのパスを返す factory。"""

    def _make(text: str, name: str = "settings.yaml") -> Path:
        """text を tmp_path/config の下の name に書く。"""
        path = tmp_path / "config" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def settings_env(
    make_settings: Callable[..., Path],
    state_dir: Path,
    log_folder: Path,
    tmp_path: Path,
) -> Callable[..., dict[str, str]]:
    """設定ファイルを書いて `RULE_INJECT_CONFIG` で指した、フックに渡す環境変数を返す factory。"""

    def _make(**global_values: Any) -> dict[str, str]:
        """記録フォルダとログのフォルダに global の値を重ねた設定ファイルを書く。"""
        values: dict[str, Any] = {"state_dir": str(state_dir), "log_dir": str(log_folder)}
        values.update(global_values)
        lines = ["global:"]
        for key, value in values.items():
            # リストは空なら `[]`、あればブロックのリストにする
            if isinstance(value, (list, tuple)):
                lines.append(f"  {key}: []" if not value else f"  {key}:")
                lines.extend(f'    - "{item}"' for item in value)
            else:
                lines.append(f'  {key}: "{value}"')
        config = make_settings("\n".join(lines) + "\n")
        return {"RULE_INJECT_CONFIG": str(config), "CLAUDE_PROJECT_DIR": str(tmp_path)}

    return _make


@pytest.fixture
def hook_env(settings_env: Callable[..., dict[str, str]]) -> dict[str, str]:
    """フックに渡す環境変数（記録フォルダ・ログのフォルダを設定ファイルで指し、プロジェクトの直下を持つ）。"""
    return settings_env()


@pytest.fixture
def xdg_state_home(tmp_path: Path) -> Path:
    """設定ファイルが読めないときのログの置き場所の元になる `XDG_STATE_HOME`（まだ作らない）。"""
    return tmp_path / "xdg_state"


@pytest.fixture
def default_log_folder(xdg_state_home: Path) -> Path:
    """`XDG_STATE_HOME` の下の既定のログのフォルダ。"""
    return xdg_state_home / "rule-inject" / "logs"


@pytest.fixture
def unreadable_env(
    tmp_path: Path,
    make_settings: Callable[..., Path],
    xdg_state_home: Path,
) -> Callable[[str], dict[str, str]]:
    """読めない設定ファイルを `RULE_INJECT_CONFIG` で指した環境変数を返す factory（種類は missing・unknown_key・broken・retention_zero）。"""
    texts = {
        "unknown_key": "global:\n  index:\n    - /a.yaml\n",
        "broken": "global: {state_dir: /s}\n",
        "retention_zero": "global:\n  log_retention_days: 0\n",
    }

    def _make(kind: str) -> dict[str, str]:
        """kind の設定ファイルを置き（missing は置かず）、`XDG_STATE_HOME` と共に環境変数にする。"""
        config = (
            tmp_path / "config" / "missing.yaml"
            if kind == "missing"
            else make_settings(texts[kind])
        )
        return {
            "RULE_INJECT_CONFIG": str(config),
            "XDG_STATE_HOME": str(xdg_state_home),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
        }

    return _make


@pytest.fixture
def unwritable() -> Iterator[Callable[[Path, int], Path]]:
    """権限を外したフォルダ・ファイルにする factory。root は権限を無視するため skip する。"""
    changed: list[tuple[Path, int]] = []

    def _apply(path: Path, mode: int) -> Path:
        """path の権限を mode にして返す。"""
        # root は権限の判定を受けないため、確かめられない
        if os.geteuid() == 0:
            pytest.skip("root は権限を無視する")
        changed.append((path, path.stat().st_mode))
        path.chmod(mode)
        return path

    yield _apply
    # 後始末で削除できるよう、権限を戻す
    for path, original in reversed(changed):
        path.chmod(original)


@pytest.fixture
def make_index(tmp_path: Path) -> Callable[..., Path]:
    """索引の YAML を書き、そのパスを返す factory。"""

    def _make(text: str, name: str = "index.yaml") -> Path:
        """text を tmp_path の下の name に書く。"""
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def index_text() -> Callable[..., str]:
    """エントリ 1 つの索引の YAML の文字列を返す factory。"""

    def _text(
        rule: str,
        *,
        paths: Sequence[str] = (),
        exclude: Sequence[str] = (),
        tools: Sequence[str] = (),
        args: Mapping[str, Sequence[str]] | None = None,
        on: Sequence[str] | None = None,
        default_on: Sequence[str] | None = None,
        read_by: Sequence[Mapping[str, Any]] = (),
    ) -> str:
        """rule と当てる条件から索引の文字列を組み立てる。"""
        lines: list[str] = []
        # 索引の既定の止める操作
        if default_on is not None:
            lines.append(f"default_on: [{', '.join(default_on)}]")
        lines.extend(["rules:", f"  - rule: {rule}"])
        # 書かれた条件だけをエントリに追加する
        for key, values in (("paths", paths), ("exclude", exclude), ("tools", tools)):
            if values:
                lines.append(f"    {key}:")
                lines.extend(f'      - "{value}"' for value in values)
        # 引数の条件は、キーごとにパターンのリストを並べたブロックのマップで書く
        if args:
            lines.append("    args:")
            for arg_key, patterns in args.items():
                lines.append(f"      {arg_key}:")
                lines.extend(f'        - "{pattern}"' for pattern in patterns)
        if on is not None:
            lines.append(f"    on: [{', '.join(on)}]")
        # 既読にする呼び出しは、`tools` のリストと任意の `args` のマップを持つ要素のブロックのリストで書く
        if read_by:
            lines.append("    read_by:")
            for condition in read_by:
                lines.append("      - tools:")
                lines.extend(f'          - "{pattern}"' for pattern in condition["tools"])
                if condition.get("args"):
                    lines.append("        args:")
                    for arg_key, patterns in condition["args"].items():
                        lines.append(f"          {arg_key}:")
                        lines.extend(f'            - "{pattern}"' for pattern in patterns)
        return "\n".join(lines) + "\n"

    return _text


@pytest.fixture
def make_entry() -> Callable[..., Any]:
    """索引のエントリ（IndexEntry）を作る factory。"""

    def _make(
        location: str,
        *,
        paths: Sequence[str] = (),
        exclude: Sequence[str] = (),
        tools: Sequence[str] = (),
        args: Mapping[str, Sequence[str]] | None = None,
        on: Sequence[str] = ("read", "write", "mcp"),
        read_by: Sequence[Mapping[str, Any]] = (),
    ) -> Any:
        """解決後の場所と当てる条件から IndexEntry を作る。"""
        from rule_inject.features.index.service import REGEX_PREFIX
        from rule_inject.features.index.types import (
            ArgCondition,
            IndexEntry,
            MatchPattern,
            ReadByCondition,
        )

        def _pattern(source: str) -> MatchPattern:
            """`re:` で始まるパターンはコンパイルし、それ以外は glob のまま MatchPattern にする。"""
            is_regex = source.startswith(REGEX_PREFIX)
            regex = re.compile(source.removeprefix(REGEX_PREFIX)) if is_regex else None
            return MatchPattern(source=source, regex=regex)

        def _arg_conditions(conditions: Mapping[str, Sequence[str]] | None) -> tuple[Any, ...]:
            """キーごとのパターンのリストから ArgCondition の並びを作る。"""
            return tuple(
                ArgCondition(key=key, patterns=tuple(_pattern(source) for source in sources))
                for key, sources in (conditions or {}).items()
            )

        return IndexEntry(
            location=location,
            paths=tuple(_pattern(source) for source in paths),
            exclude=tuple(_pattern(source) for source in exclude),
            tools=tuple(_pattern(source) for source in tools),
            args=_arg_conditions(args),
            on=frozenset(on),
            read_by=tuple(
                ReadByCondition(
                    tools=tuple(_pattern(source) for source in condition["tools"]),
                    args=_arg_conditions(condition.get("args")),
                )
                for condition in read_by
            ),
        )

    return _make


@pytest.fixture
def rule_file(tmp_path: Path) -> Callable[..., Path]:
    """ルールの本文のファイルを置く factory。"""

    def _make(name: str = "python.md", body: str = "# 規約\n") -> Path:
        """tmp_path/rules の下に name のファイルを body で置く。"""
        path = tmp_path / "rules" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    return _make


@pytest.fixture
def write_record(state_dir: Path, session_id: str) -> Callable[[Sequence[str]], Path]:
    """既読の記録ファイルを、行を 1 行ずつ書いて置く factory（既読の行は `{場所}\\t{ハッシュ}`）。"""

    def _write(lines: Sequence[str]) -> Path:
        """lines を 1 行ずつ、このセッションの記録ファイルに書く。"""
        path = state_dir / f"{session_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_guided(state_dir: Path, session_id: str) -> Callable[[Sequence[str]], Path]:
    """案内済みの記録ファイルを、場所を 1 行ずつ書いて置く factory。"""

    def _write(locations: Sequence[str]) -> Path:
        """locations を 1 行ずつ、このセッションの案内済みの記録ファイルに書く。"""
        path = state_dir / f"{session_id}.guided.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{location}\n" for location in locations), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_aged_record(state_dir: Path) -> Callable[..., Path]:
    """最終更新を過去に戻した記録ファイルを、指定のセッションで置く factory。"""

    def _write(
        target_session_id: str,
        age_days: int,
        *,
        base: float | None = None,
        suffix: str = ".txt",
    ) -> Path:
        """target_session_id の記録ファイル（suffix の名前）を置き、最終更新を base の age_days 日前にする。"""
        path = state_dir / f"{target_session_id}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("/r/a.md\n", encoding="utf-8")
        # 基準の時刻が無ければ実際の現在から戻す
        reference = time.time() if base is None else base
        modified = reference - age_days * SECONDS_PER_DAY
        os.utime(path, (modified, modified))
        return path

    return _write


@pytest.fixture
def read_lines() -> Callable[[Path], list[str]]:
    """ファイルを UTF-8 で読み、行のリストを返す。"""

    def _read(path: Path) -> list[str]:
        """path の行を返す。"""
        return path.read_text(encoding="utf-8").splitlines()

    return _read


@pytest.fixture
def read_history(state_dir: Path, session_id: str) -> Callable[[], list[dict[str, Any]]]:
    """このセッションの既読の履歴ファイル（JSON Lines）を読み、1 行ごとの dict を返す。"""

    def _read() -> list[dict[str, Any]]:
        """{session_id}.history.jsonl の各行を JSON として読む。"""
        text = (state_dir / f"{session_id}.history.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    return _read


@pytest.fixture
def read_logs_in() -> Callable[[Path], list[dict[str, Any]]]:
    """フォルダの日付ごとのログ（JSON Lines）を日付の順に読み、1 行ごとの dict を返す関数。"""

    def _read(folder: Path) -> list[dict[str, Any]]:
        """folder の {yyyymmdd}_rule-inject.log の各行を JSON として読む。"""
        texts = [
            path.read_text(encoding="utf-8") for path in sorted(folder.glob("*_rule-inject.log"))
        ]
        return [json.loads(line) for text in texts for line in text.splitlines()]

    return _read


@pytest.fixture
def read_daily_log(
    log_folder: Path,
    read_logs_in: Callable[[Path], list[dict[str, Any]]],
) -> Callable[[], list[dict[str, Any]]]:
    """ログのフォルダの日付ごとのログを読み、1 行ごとの dict を返す関数。"""

    def _read() -> list[dict[str, Any]]:
        """ログのフォルダの {yyyymmdd}_rule-inject.log の各行を読む。"""
        return read_logs_in(log_folder)

    return _read


@pytest.fixture
def read_default_log(
    default_log_folder: Path,
    read_logs_in: Callable[[Path], list[dict[str, Any]]],
) -> Callable[[], list[dict[str, Any]]]:
    """既定のログのフォルダの日付ごとのログを読み、1 行ごとの dict を返す関数。"""

    def _read() -> list[dict[str, Any]]:
        """既定のログのフォルダの {yyyymmdd}_rule-inject.log の各行を読む。"""
        return read_logs_in(default_log_folder)

    return _read


@pytest.fixture
def write_dated_log(log_folder: Path) -> Callable[[date], Path]:
    """日付を名前に持つログのファイルを、ログのフォルダに置く factory。"""

    def _write(day: date) -> Path:
        """day の日付の `{yyyymmdd}_rule-inject.log` をログのフォルダに置く。"""
        path = log_folder / f"{day:%Y%m%d}_rule-inject.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        return path

    return _write


@pytest.fixture
def hook_payload(tmp_path: Path, session_id: str) -> Callable[..., dict[str, Any]]:
    """フックの標準入力の JSON（dict）を作る factory。"""

    def _make(
        event: str,
        *,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        cwd: Path | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """出来事の名前とツールの入力から、フックの入力を組み立てる。"""
        payload: dict[str, Any] = {
            "session_id": session_id,
            "cwd": str(cwd or tmp_path),
            "hook_event_name": event,
        }
        # ツールを呼ぶ出来事にだけ、ツール名と入力が届く
        if tool_name is not None:
            payload["tool_name"] = tool_name
            payload["tool_input"] = tool_input or {}
        payload.update(extra)
        return payload

    return _make
