"""shared/settings.py の単体テスト。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.settings import _matches_project, load_settings


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """起動したプロジェクトの直下（`CLAUDE_PROJECT_DIR`）。"""
    path = tmp_path / "repo"
    path.mkdir()
    return path


def test_load_settings(
    tmp_path: Path,
    project_dir: Path,
    make_settings: Callable[..., Path],
) -> None:
    """設定ファイルの値を使う（正常系）。"""
    # 準備
    (project_dir / "rules.yaml").write_text("rules: []\n", encoding="utf-8")
    config = make_settings(
        "global:\n"
        "  indexes:\n"
        "    - /g/rules.yaml\n"
        f"  state_dir: {tmp_path / 'state'}\n"
        f"  log_dir: {tmp_path / 'logs'}\n"
        "  record_retention_days: 7\n"
        "  log_retention_days: 5\n"
        "projects:\n"
        f"  - match: {project_dir.name}\n"
        "    indexes:\n"
        "      - rules/a.yaml\n"
    )
    env = {"RULE_INJECT_CONFIG": str(config), "CLAUDE_PROJECT_DIR": str(project_dir)}
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == ("/g/rules.yaml", str(project_dir / "rules" / "a.yaml"))
    assert result.state_dir == tmp_path / "state"
    assert result.log_dir == tmp_path / "logs"
    assert result.record_retention_days == 7
    assert result.log_retention_days == 5


def test_load_settings_when_no_config(tmp_path: Path, project_dir: Path) -> None:
    """`RULE_INJECT_CONFIG` が無ければ既定値を使う（正常系）。"""
    # 準備
    user_index = tmp_path / "xdg_config" / "rule-inject" / "rules.yaml"
    user_index.parent.mkdir(parents=True)
    user_index.write_text("rules: []\n", encoding="utf-8")
    project_index = project_dir / "rules.yaml"
    project_index.write_text("rules: []\n", encoding="utf-8")
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "XDG_STATE_HOME": str(tmp_path / "xdg_state"),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == (str(user_index), str(project_index))
    assert result.state_dir == tmp_path / "xdg_state" / "rule-inject"
    assert result.log_dir == tmp_path / "xdg_state" / "rule-inject" / "logs"
    assert result.record_retention_days == 30
    assert result.log_retention_days == 3


def test_load_settings_when_default_missing(tmp_path: Path, project_dir: Path) -> None:
    """既定の置き場所に索引が無ければ並べない（正常系）。"""
    # 準備
    (tmp_path / "xdg_config").mkdir()
    env = {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == ()


def test_load_settings_when_projects_order(
    project_dir: Path,
    make_settings: Callable[..., Path],
) -> None:
    """当たった要素を並びの順に重ねる（正常系）。"""
    # 準備
    config = make_settings(
        "global:\n"
        "  indexes: [/g.yaml]\n"
        "projects:\n"
        f"  - match: {project_dir.name}\n"
        "    indexes: [/a.yaml]\n"
        "  - match: other\n"
        "    indexes: [/b.yaml]\n"
        f"  - match: {project_dir}\n"
        "    indexes: [/c.yaml]\n"
    )
    env = {"RULE_INJECT_CONFIG": str(config), "CLAUDE_PROJECT_DIR": str(project_dir)}
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == ("/g.yaml", "/a.yaml", "/c.yaml")


def test_load_settings_when_indexes_empty(
    tmp_path: Path,
    project_dir: Path,
    make_settings: Callable[..., Path],
) -> None:
    """空の並びは既定の置き場所も読まない（正常系）。"""
    # 準備
    user_index = tmp_path / "xdg_config" / "rule-inject" / "rules.yaml"
    user_index.parent.mkdir(parents=True)
    user_index.write_text("rules: []\n", encoding="utf-8")
    (project_dir / "rules.yaml").write_text("rules: []\n", encoding="utf-8")
    config = make_settings(
        f"global:\n  indexes: []\nprojects:\n  - match: {project_dir.name}\n    indexes: []\n"
    )
    env = {
        "RULE_INJECT_CONFIG": str(config),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg_config"),
        "CLAUDE_PROJECT_DIR": str(project_dir),
    }
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == ()


def test_load_settings_when_no_project_dir(
    project_dir: Path,
    make_settings: Callable[..., Path],
) -> None:
    """`CLAUDE_PROJECT_DIR` が無ければどの要素も当てない（正常系）。"""
    # 準備
    config = make_settings(
        "global:\n"
        "  indexes: [/g.yaml]\n"
        "projects:\n"
        f"  - match: {project_dir}\n"
        "    indexes: [/a.yaml]\n"
        f"  - match: {project_dir.name}\n"
        "    indexes: [/b.yaml]\n"
    )
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行
    result = load_settings(env)
    # 検証
    assert result.indexes == ("/g.yaml",)


def test_load_settings_when_home(isolated_home: Path) -> None:
    """`RULE_INJECT_CONFIG` の `~` を展開する（正常系）。"""
    # 準備
    config = isolated_home / "c" / "settings.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("global:\n  log_retention_days: 5\n", encoding="utf-8")
    env = {"RULE_INJECT_CONFIG": "~/c/settings.yaml"}
    # 実行
    result = load_settings(env)
    # 検証
    assert result.log_retention_days == 5


def test_load_settings_when_missing(tmp_path: Path) -> None:
    """指したファイルが無ければ拒む（異常系）。"""
    # 準備
    missing = tmp_path / "missing.yaml"
    env = {"RULE_INJECT_CONFIG": str(missing)}
    # 実行・検証
    with pytest.raises(SettingsReadError, match="FileNotFoundError") as raised:
        load_settings(env)
    assert raised.value.path == str(missing)


def test_load_settings_when_unknown_key(make_settings: Callable[..., Path]) -> None:
    """知らないキーを拒む（異常系）。"""
    # 準備
    config = make_settings("projects:\n  - match: repo\n    index:\n      - /a.yaml\n")
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError, match=r"\d+行目") as raised:
        load_settings(env)
    assert raised.value.path == str(config)
    assert "index" in raised.value.reason


@pytest.mark.parametrize(
    ("text", "key", "value"),
    [
        pytest.param(
            "global:\n  indexes:\n    - rules.yaml\n",
            "global.indexes",
            "rules.yaml",
            id="indexes",
        ),
        pytest.param("global:\n  state_dir: state\n", "global.state_dir", "state", id="state_dir"),
        pytest.param("global:\n  log_dir: logs\n", "global.log_dir", "logs", id="log_dir"),
    ],
)
def test_load_settings_when_relative_global_path(
    make_settings: Callable[..., Path],
    text: str,
    key: str,
    value: str,
) -> None:
    """`global` の相対パスを拒む（異常系）。"""
    # 準備
    config = make_settings(text)
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert key in raised.value.reason
    assert value in raised.value.reason


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("record_retention_days", id="record"),
        pytest.param("log_retention_days", id="log"),
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("0", id="zero"),
        pytest.param("-1", id="negative"),
        pytest.param("abc", id="not_number"),
        pytest.param("1.5", id="decimal"),
    ],
)
def test_load_settings_when_invalid_retention(
    make_settings: Callable[..., Path],
    key: str,
    value: str,
) -> None:
    """1 以上の整数でない保持日数を拒む（異常系）。"""
    # 準備
    config = make_settings(f"global:\n  {key}: {value}\n")
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert f"global.{key}" in raised.value.reason
    assert value in raised.value.reason


def test_load_settings_when_match_missing(make_settings: Callable[..., Path]) -> None:
    """`match` の無い要素を拒む（異常系）。"""
    # 準備
    config = make_settings("projects:\n  - indexes:\n      - /a.yaml\n")
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert "projects[0].match" in raised.value.reason


def test_load_settings_when_not_utf8(tmp_path: Path) -> None:
    """UTF-8 として読めない設定ファイルを拒む（異常系）。"""
    # 準備
    config = tmp_path / "settings.yaml"
    config.write_bytes(b"\xff\xfe")
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert raised.value.path == str(config)


@pytest.mark.parametrize(
    ("current_dir", "expected"),
    [
        pytest.param("/w/repo", True, id="same"),
        pytest.param("/w/repo/sub", True, id="under"),
        pytest.param("/w/repo2", False, id="prefix_only"),
    ],
)
def test_matches_project_when_absolute(current_dir: str, expected: bool) -> None:
    """絶対パスはそのパスと配下に当てる（正常系）。"""
    # 実行
    result = _matches_project("/w/repo", current_dir)
    # 検証
    assert result is expected


@pytest.mark.parametrize(
    ("current_dir", "expected"),
    [
        pytest.param("/w/repo", True, id="same_name"),
        pytest.param("/w/other", False, id="other_name"),
    ],
)
def test_matches_project_when_name(current_dir: str, expected: bool) -> None:
    """プロジェクト名はフォルダ名で当てる（正常系）。"""
    # 実行
    result = _matches_project("repo", current_dir)
    # 検証
    assert result is expected


@pytest.mark.parametrize(
    ("match", "expected"),
    [
        pytest.param("repo", True, id="name"),
        pytest.param("/w/repo", True, id="absolute"),
        pytest.param("feat", False, id="worktree_name"),
    ],
)
def test_matches_project_when_worktree(match: str, expected: bool) -> None:
    """worktree は本体で当てる（正常系）。"""
    # 実行
    result = _matches_project(match, "/w/repo/.claude/worktrees/feat")
    # 検証
    assert result is expected


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("1023", id="below_range"),
        pytest.param("65536", id="above_range"),
        pytest.param("abc", id="not_number"),
    ],
)
def test_load_settings_when_invalid_server_port(
    make_settings: Callable[..., Path],
    value: str,
) -> None:
    """範囲の外のポートを拒む（異常系）。"""
    # 準備
    config = make_settings(f"global:\n  server_port: {value}\n")
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert "global.server_port" in raised.value.reason
    assert value in raised.value.reason


@pytest.mark.parametrize(
    ("global_text", "expected"),
    [
        pytest.param("global:\n  server_port: 9000\n", 9000, id="from_config"),
        pytest.param("global:\n  log_retention_days: 5\n", 8783, id="default"),
    ],
)
def test_load_settings_when_server_port(
    make_settings: Callable[..., Path],
    global_text: str,
    expected: int,
) -> None:
    """ポートを設定ファイルから読み、無ければ既定にする（正常系）。"""
    # 準備
    config = make_settings(global_text)
    env = {"RULE_INJECT_CONFIG": str(config)}
    # 実行
    settings = load_settings(env)
    # 検証
    assert settings.server_port == expected


@pytest.mark.parametrize(
    "global_text",
    [
        pytest.param("global:\n  server_port: 9000\n", id="config_has_port"),
        pytest.param(None, id="no_config"),
    ],
)
def test_load_settings_when_port_env(
    make_settings: Callable[..., Path],
    global_text: str | None,
) -> None:
    """環境変数のポートが設定ファイルより優先する（正常系）。"""
    # 準備
    env = {"RULE_INJECT_PORT": "9100"}
    if global_text is not None:
        env["RULE_INJECT_CONFIG"] = str(make_settings(global_text))
    # 実行
    settings = load_settings(env)
    # 検証
    assert settings.server_port == 9100


def test_load_settings_when_invalid_port_env() -> None:
    """許す範囲の外の環境変数のポートを拒む（異常系）。"""
    # 準備
    env = {"RULE_INJECT_PORT": "80"}
    # 実行・検証
    with pytest.raises(SettingsReadError) as raised:
        load_settings(env)
    assert raised.value.path == "RULE_INJECT_PORT"
    assert "80" in raised.value.reason
