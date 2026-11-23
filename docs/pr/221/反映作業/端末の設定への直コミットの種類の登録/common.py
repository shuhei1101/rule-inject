"""端末の設定への直コミットの種類の登録で、疎通確認・実行・確認が共有する固定値と読み取り。"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SOURCE_ID = "rule-inject"
BASE_URL = "http://127.0.0.1:8786"
SETTINGS_PATH = Path.home() / ".config/project-index/settings.yaml"
# 環境変数 RULE_INJECT_SOURCE_CONFIG で上書きできる（マージの前の dry-run で作業ブランチの設定を指す）
SOURCE_CONFIG_PATH = Path(
    os.environ.get(
        "RULE_INJECT_SOURCE_CONFIG",
        "/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop/project-index.yaml",
    )
)
KINDS = [
    "architecture",
    "nonfunctional",
    "scenario",
    "interface",
    "module",
    "config",
    "er",
    "data",
    "external_api",
    "library",
    "test_procedure",
    "layout",
    "dev_command",
    "agent",
    "mcp_server",
    "launch",
    "agent_flow",
    "llm_call",
    "evaluation",
    "eval_criterion",
    "eval_case",
    "index",
    "glossary",
    "rule_index",
    "docs",
    "src",
    "hooks",
    "tests",
    "skills",
    "root",
]
# 一時的な通信エラーの再試行（3 回・2 秒間隔）
RETRIES = 3
RETRY_INTERVAL_SEC = 2
TIMEOUT_SEC = 10
HTTP_OK = 200
HTTP_SERVER_ERROR = 500
HTTP_CONFLICT = 409


def request(
    method: str, path: str, body: dict[str, Any] | None = None, *, retry: bool = True
) -> tuple[int, Any]:
    """project-index の HTTP の API を呼び、状態と JSON の本文を返す。

    `retry` が真なら 5xx と接続の失敗を再試行する。書き込みは `retry=False` で呼ぶ。
    """
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    last: Exception | None = None
    for attempt in range(RETRIES if retry else 1):
        req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as res:
                return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as error:
            if error.code < HTTP_SERVER_ERROR:
                return error.code, json.loads(error.read() or b"null")
            last = error
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
        if retry and attempt + 1 < RETRIES:
            time.sleep(RETRY_INTERVAL_SEC)
    raise RuntimeError(f"{method} {path}: {last}")


def source_row(view: dict[str, Any]) -> dict[str, Any] | None:
    """`GET /settings/sources` の応答から rule-inject の行を返す。"""
    for row in view.get("sources", []):
        if row.get("id") == SOURCE_ID:
            return dict(row)
    return None


def current_write_api_kinds(row: dict[str, Any]) -> list[str]:
    """行の `direct_commit.write_api_kinds` を返す（無ければ空）。"""
    direct_commit = row.get("directCommit") or row.get("direct_commit") or {}
    kinds = direct_commit.get("writeApiKinds", direct_commit.get("write_api_kinds", []))
    return list(kinds)


def config_kind_ids() -> list[str]:
    """develop の worktree の `project-index.yaml` の `direct_commit.kinds[]` の ID を、行の文字列から読む。"""
    ids: list[str] = []
    in_kinds = False
    for line in SOURCE_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        if line == "  kinds:":
            in_kinds = True
            continue
        if in_kinds:
            stripped = line.strip()
            if not stripped.startswith("- "):
                break
            item = stripped[2:]
            if item.startswith("{id: "):
                item = item[len("{id: ") :].split(",")[0].rstrip("}")
            ids.append(item)
    return ids


def set_write_api_kinds(kinds: list[str]) -> tuple[bool, str]:
    """rule-inject の行の `write_api_kinds` を `kinds` にする。成否と失敗の内容を返す。

    PATCH は再試行に乗せず、失敗したら GET で適用済みかを判定し直し、未適用なら取り直した
    `version` で送り直す。
    """
    detail = ""
    for attempt in range(RETRIES):
        status, view = request("GET", "/settings/sources")
        row = source_row(view) if status == HTTP_OK else None
        if row is None:
            return False, f"GET /settings/sources: HTTP {status}・{SOURCE_ID} の行が無い"
        if current_write_api_kinds(row) == kinds:
            return True, ""
        if attempt > 0:
            time.sleep(RETRY_INTERVAL_SEC)
        body = {
            "expectedVersion": view["version"],
            "source": {"direct_commit": {"write_api_kinds": kinds}},
        }
        try:
            status, result = request("PATCH", f"/settings/sources/{SOURCE_ID}", body, retry=False)
        except RuntimeError as error:
            detail = str(error)
            continue
        if status == HTTP_OK:
            return True, ""
        detail = f"PATCH /settings/sources/{SOURCE_ID}: HTTP {status} {result}"
        if status != HTTP_CONFLICT and status < HTTP_SERVER_ERROR:
            return False, detail
    return False, detail
