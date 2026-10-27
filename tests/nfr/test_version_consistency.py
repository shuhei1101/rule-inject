"""非機能要件「バージョンの一致」のテスト。"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_NAME = "rule-inject"
VERSION_INI = "version.ini"
PYPROJECT = "pyproject.toml"
UV_LOCK = "uv.lock"
PLUGIN_JSON = "plugin.json"
PLUGIN_DIR = ".claude-plugin"


class VersionMismatchError(Exception):
    """バージョンを持つファイルの値が食い違ったときの例外。"""


def _read_versions(root: Path) -> dict[str, str]:
    """root の下の 4 つのファイルからバージョンを、ファイル名ごとに原文のまま取り出す。"""
    version_ini = (root / VERSION_INI).read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))
    uv_lock = tomllib.loads((root / UV_LOCK).read_text(encoding="utf-8"))
    plugin = json.loads((root / PLUGIN_DIR / PLUGIN_JSON).read_text(encoding="utf-8"))
    # uv.lock のパッケージのうち、自分自身の行だけを選ぶ
    lock_versions = [p["version"] for p in uv_lock["package"] if p["name"] == PACKAGE_NAME]
    # 自分自身の行が 1 件でなければ、バージョンを決められない
    if len(lock_versions) != 1:
        raise ValueError(f"{UV_LOCK} の {PACKAGE_NAME} が {len(lock_versions)} 件あります")
    return {
        VERSION_INI: version_ini,
        PYPROJECT: pyproject["project"]["version"],
        UV_LOCK: lock_versions[0],
        PLUGIN_JSON: plugin["version"],
    }


def _check_version_consistency(root: Path) -> None:
    """4 つのファイルのバージョンが一致することを確かめ、食い違えば 4 つの値を並べた例外を投げる。"""
    versions = _read_versions(root)
    # version.ini だけ先頭の v を除いて比べる
    comparable = {
        name: value.removeprefix("v") if name == VERSION_INI else value
        for name, value in versions.items()
    }
    # 値が 2 種類以上あれば食い違い
    if len(set(comparable.values())) > 1:
        listed = ", ".join(f"{name}={value}" for name, value in versions.items())
        raise VersionMismatchError(f"バージョンが食い違っています: {listed}")


def _write_version_files(
    root: Path, *, version_ini: str, pyproject: str, uv_lock: str, plugin: str
) -> None:
    """root の下に、バージョンだけを引数で変えた 4 つのファイルを置く。"""
    (root / VERSION_INI).write_text(f"{version_ini}\n", encoding="utf-8")
    (root / PYPROJECT).write_text(
        f'[project]\nname = "{PACKAGE_NAME}"\nversion = "{pyproject}"\n', encoding="utf-8"
    )
    # 自分自身より前に別のパッケージを置き、名前で選べることも確かめる
    (root / UV_LOCK).write_text(
        '[[package]]\nname = "mcp"\nversion = "2.2.0"\n\n'
        f'[[package]]\nname = "{PACKAGE_NAME}"\nversion = "{uv_lock}"\n',
        encoding="utf-8",
    )
    plugin_dir = root / PLUGIN_DIR
    plugin_dir.mkdir()
    (plugin_dir / PLUGIN_JSON).write_text(
        json.dumps({"name": PACKAGE_NAME, "version": plugin}), encoding="utf-8"
    )


def test_version_consistency_when_all_match() -> None:
    """4 つのバージョンが一致するとき、検査が通る（正常系）。"""
    # 実行・検証
    _check_version_consistency(REPO_ROOT)


def test_version_consistency_when_mismatch(tmp_path: Path) -> None:
    """バージョンが 1 つでも食い違うとき、検査が 4 つの値を並べて fail する（異常系）。"""
    # 準備
    _write_version_files(
        tmp_path, version_ini="v0.1.1", pyproject="0.1.1", uv_lock="0.1.1", plugin="0.1.0"
    )
    # 実行
    with pytest.raises(VersionMismatchError) as exc_info:
        _check_version_consistency(tmp_path)
    # 検証
    message = str(exc_info.value)
    assert "version.ini=v0.1.1" in message
    assert "pyproject.toml=0.1.1" in message
    assert "uv.lock=0.1.1" in message
    assert "plugin.json=0.1.0" in message
