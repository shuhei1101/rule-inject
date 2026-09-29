"""単体テストが共有する fixture。"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

SESSION_ID = "2f9c1b7e-0d54-4b7a-9d4f-5c3a1e2b7f10"


@pytest.fixture
def session_id() -> str:
    """テストで使うセッションの識別子。"""
    return SESSION_ID


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """既読の記録とログを置く記録フォルダ（まだ作らない）。"""
    return tmp_path / "state"


@pytest.fixture
def hook_env(state_dir: Path, tmp_path: Path) -> dict[str, str]:
    """フックと MCP サーバーに渡す環境変数（記録フォルダとプロジェクトの直下だけ）。"""
    return {
        "RULE_INJECT_STATE_DIR": str(state_dir),
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }


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
    """エントリ 1 つの索引の YAML の文字列を返す factory。"""

    def _text(
        rule: str,
        *,
        paths: Sequence[str] = (),
        exclude: Sequence[str] = (),
        tools: Sequence[str] = (),
        on: Sequence[str] | None = None,
        default_on: Sequence[str] | None = None,
    ) -> str:
        """rule と当てる条件から索引の文字列を組み立てる。"""
        lines: list[str] = []
        # 索引の既定の止める操作
        if default_on is not None:
            lines.append(f"default_on: [{', '.join(default_on)}]")
        lines.extend(["rules:", f"  - rule: {rule}"])
        # 書かれた条件だけをエントリに足す
        for key, values in (("paths", paths), ("exclude", exclude), ("tools", tools)):
            if values:
                lines.append(f"    {key}:")
                lines.extend(f'      - "{value}"' for value in values)
        if on is not None:
            lines.append(f"    on: [{', '.join(on)}]")
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
        on: Sequence[str] = ("read", "write", "mcp"),
    ) -> Any:
        """解決後の場所と当てる条件から IndexEntry を作る。"""
        from rule_inject.features.index.types import IndexEntry

        return IndexEntry(
            location=location,
            paths=tuple(paths),
            exclude=tuple(exclude),
            tools=tuple(tools),
            on=frozenset(on),
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
    """既読の記録ファイルを、場所を 1 行ずつ書いて置く factory。"""

    def _write(locations: Sequence[str]) -> Path:
        """locations を 1 行ずつ、このセッションの記録ファイルに書く。"""
        path = state_dir / f"{session_id}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{location}\n" for location in locations), encoding="utf-8")
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
def read_log(state_dir: Path) -> Callable[[], list[dict[str, Any]]]:
    """記録フォルダのログ（JSON Lines）を読み、1 行ごとの dict を返す。"""

    def _read() -> list[dict[str, Any]]:
        """rule-inject.log の各行を JSON として読む。"""
        text = (state_dir / "rule-inject.log").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    return _read


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
