"""結合テストが共有する fixture。フックは子プロセスとして起動し、標準入力へ JSON を渡す。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest

SESSION_ID = "2f9c1b7e-0d54-4b7a-9d4f-5c3a1e2b7f10"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOK_RUN = PROJECT_ROOT / "hooks" / "run.py"
HOOK_TIMEOUT_SEC = 30
SECONDS_PER_DAY = 86_400


@pytest.fixture
def session_id() -> str:
    """テストで使うセッションの識別子。"""
    return SESSION_ID


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """既読の記録とログを置く記録フォルダ（まだ作らない）。"""
    return tmp_path / "state"


@pytest.fixture
def log_folder(tmp_path: Path) -> Path:
    """日付ごとのログを置くログのフォルダ（まだ作らない）。"""
    return tmp_path / "logs"


@pytest.fixture
def base_env(state_dir: Path, log_folder: Path, tmp_path: Path) -> dict[str, str]:
    """このプラグインの環境変数を外し、記録フォルダ・ログのフォルダ・プロジェクトの直下・索引の無い設定フォルダだけを足した環境変数。"""
    env = {name: value for name, value in os.environ.items() if not name.startswith("RULE_INJECT_")}
    env["RULE_INJECT_STATE_DIR"] = str(state_dir)
    env["RULE_INJECT_LOG_DIR"] = str(log_folder)
    env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    # 既定の索引が実際の設定フォルダの索引を読まないよう、索引の無い一時フォルダを指す
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    return env


@pytest.fixture
def run_hook(base_env: dict[str, str]) -> Callable[..., subprocess.CompletedProcess[str]]:
    """フックを子プロセスとして起動し、標準入力へ JSON を渡して結果を返す factory。"""

    def _run(
        name: str,
        payload: dict[str, Any],
        *,
        index: Path | str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """hooks/run.py に name を渡して起動する。index があればプロジェクト用の索引として指し、extra_env を環境変数に足す。"""
        env = {**base_env, **(extra_env or {})}
        if index is not None:
            env["RULE_INJECT_INDEXES_PROJECT"] = str(index)
        return subprocess.run(
            [sys.executable, str(HOOK_RUN), name],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            timeout=HOOK_TIMEOUT_SEC,
            check=False,
        )

    return _run


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
    # 後始末で消せるよう、権限を戻す
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
    """エントリの dict を並べた索引の YAML の文字列を返す factory。"""

    def _text(*entries: Mapping[str, Any], default_on: Sequence[str] | None = None) -> str:
        """各エントリの rule・paths・exclude・tools・args・on・read_by から索引の文字列を組み立てる。"""
        lines: list[str] = []
        # 索引の既定の止める操作
        if default_on is not None:
            lines.append(f"default_on: [{', '.join(default_on)}]")
        lines.append("rules:")
        for entry in entries:
            lines.append(f"  - rule: {entry['rule']}")
            # 書かれた条件だけをエントリに足す
            for key in ("paths", "exclude", "tools"):
                if entry.get(key):
                    lines.append(f"    {key}:")
                    lines.extend(f'      - "{value}"' for value in entry[key])
            # 引数の条件は、キーごとにパターンのリストを並べたブロックのマップで書く
            if entry.get("args"):
                lines.append("    args:")
                for arg_key, patterns in entry["args"].items():
                    lines.append(f"      {arg_key}:")
                    lines.extend(f'        - "{pattern}"' for pattern in patterns)
            if entry.get("on") is not None:
                lines.append(f"    on: [{', '.join(entry['on'])}]")
            # 既読にする呼び出しは、`tools` のリストと任意の `args` のマップを持つ要素のブロックのリストで書く
            if entry.get("read_by"):
                lines.append("    read_by:")
                for condition in entry["read_by"]:
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
    """既読の記録ファイルを、場所を 1 行ずつ書いて置く factory。"""

    def _write(locations: Sequence[str], name: str | None = None) -> Path:
        """locations を 1 行ずつ、name（無ければこのセッション）の記録ファイルに書く。"""
        path = state_dir / f"{name or session_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{location}\n" for location in locations), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_guided(state_dir: Path, session_id: str) -> Callable[..., Path]:
    """案内済みの記録ファイルを、場所を 1 行ずつ書いて置く factory。"""

    def _write(locations: Sequence[str], name: str | None = None) -> Path:
        """locations を 1 行ずつ、name（無ければこのセッション）の案内済みの記録ファイルに書く。"""
        path = state_dir / f"{name or session_id}.guided.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{location}\n" for location in locations), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def write_history(state_dir: Path, session_id: str) -> Callable[..., Path]:
    """既読の履歴ファイルを、1 行の JSON を書いて置く factory。"""

    def _write(name: str | None = None) -> Path:
        """name（無ければこのセッション）の既読の履歴ファイルに 1 行の JSON を書く。"""
        target = name or session_id
        path = state_dir / f"{target}.history.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "time": "2026-10-24T09:30:00Z",
            "session_id": target,
            "method": "read",
            "tool": "Read",
            "location": "/r/a.md",
        }
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        return path

    return _write


@pytest.fixture
def read_history(state_dir: Path, session_id: str) -> Callable[[], list[dict[str, Any]]]:
    """このセッションの既読の履歴ファイル（JSON Lines）を読み、1 行ごとの dict を返す。"""

    def _read() -> list[dict[str, Any]]:
        """{session_id}.history.jsonl の各行を JSON として読む。"""
        text = (state_dir / f"{session_id}.history.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    return _read


@pytest.fixture
def set_age_days() -> Callable[[Path, int], Path]:
    """ファイルの最終更新を、現在から指定の日数前に戻す factory。"""

    def _set(path: Path, age_days: int) -> Path:
        """path の最終更新を age_days 日前にして返す。"""
        modified = time.time() - age_days * SECONDS_PER_DAY
        os.utime(path, (modified, modified))
        return path

    return _set


@pytest.fixture
def read_lines() -> Callable[[Path], list[str]]:
    """ファイルを UTF-8 で読み、行のリストを返す。"""

    def _read(path: Path) -> list[str]:
        """path の行を返す。"""
        return path.read_text(encoding="utf-8").splitlines()

    return _read


@pytest.fixture
def read_log(log_folder: Path) -> Callable[[], list[dict[str, Any]]]:
    """ログのフォルダの日付ごとのログ（JSON Lines）を日付の順に読み、1 行ごとの dict を返す。"""

    def _read() -> list[dict[str, Any]]:
        """{yyyymmdd}_rule-inject.log の各行を JSON として読む。"""
        texts = [
            path.read_text(encoding="utf-8")
            for path in sorted(log_folder.glob("*_rule-inject.log"))
        ]
        return [json.loads(line) for text in texts for line in text.splitlines()]

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
