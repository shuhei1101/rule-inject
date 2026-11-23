"""端末の設定への直コミットの種類の登録で、疎通確認・実行・確認が共有する固定値と読み取り。"""

import json
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
SOURCE_CONFIG_PATH = Path(
    "/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop/project-index.yaml"
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


def request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    """project-index の HTTP の API を呼び、状態と JSON の本文を返す。5xx と接続の失敗は再試行する。"""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    last: Exception | None = None
    for attempt in range(RETRIES):
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
        if attempt + 1 < RETRIES:
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
