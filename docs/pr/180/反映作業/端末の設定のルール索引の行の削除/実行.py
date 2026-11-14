#!/usr/bin/env python3
"""端末の設定の rule-inject の rule_indexes から docs/rules.yaml の行を削除し、モニターに読み直させる。"""

import difflib
import json
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

import yaml

SETTINGS = Path.home() / ".config/ai-monitor/settings.yaml"
BACKUP = Path.home() / ".config/ai-monitor/settings.yaml.bak-pr180"
PORT_FILE = Path("/mnt/c/Users/shuhe/repo/ai-monitor/data/monitor.port")
REMOVED = "/mnt/c/Users/shuhe/repo/rule-inject/docs/rules.yaml"
KEPT = "/mnt/c/Users/shuhe/repo/rule-inject/rules.yaml"
PROJECT = "rule-inject"


def rule_indexes(text: str) -> list[str]:
    data = yaml.safe_load(text) or {}
    for project in data.get("projects") or []:
        if project.get("name") == PROJECT:
            return list(project.get("rule_indexes") or [])
    raise LookupError(f"projects に {PROJECT} がありません")


def fail(step: str, command: str, err: object) -> None:
    print(f"{step}: failed", flush=True)
    print(f"$ {command}\n{err}", file=sys.stderr)
    sys.exit(1)


args = sys.argv[1:]
dry_run = args == ["--dry-run"]
if args and not dry_run:
    fail("前提確認", " ".join(sys.argv), "受け付ける引数は無しか --dry-run だけです")

# 前提確認
if not SETTINGS.is_file():
    fail("前提確認", f"test -f {SETTINGS}", "ファイルがありません")
if Path(REMOVED).exists():
    fail("前提確認", f"test ! -e {REMOVED}", "削除する索引がまだクローン本体にあります（master へ入った後に実行する）")
current = SETTINGS.read_text(encoding="utf-8")
try:
    before = rule_indexes(current)
except Exception as exc:  # noqa: BLE001
    fail("前提確認", f"yaml.safe_load({SETTINGS})", exc)
if KEPT not in before:
    fail("前提確認", f"grep {KEPT} {SETTINGS}", "直下の rules.yaml が rule_indexes にありません")
print("前提確認: ok")

# 計画（--dry-run もここを通る）
lines = current.splitlines(keepends=True)
new_lines = [line for line in lines if line.strip() != f"- {REMOVED}"]
removed = len(lines) - len(new_lines)
if removed == 0:
    print("設定の書き換え: skipped")
    sys.exit(0)
if removed > 1:
    fail("前提確認", f"grep -c '- {REMOVED}' {SETTINGS}", f"{removed} 行あり、想定の上限 1 行を超えています")
new_text = "".join(new_lines)
sys.stdout.writelines(difflib.unified_diff(lines, new_lines, str(SETTINGS), str(SETTINGS)))
if dry_run:
    print("設定の書き換え: changed")
    print("設定の再読込: changed")
    sys.exit(0)

# 適用（検証 → 退避 → 置き換え）
try:
    after = rule_indexes(new_text)
except Exception as exc:  # noqa: BLE001
    fail("検証", "yaml.safe_load(書き換えた内容)", exc)
if REMOVED in after or after != [i for i in before if i != REMOVED]:
    fail("検証", "rule_indexes の比較", f"書き換え後の rule_indexes が想定と違います: {after}")
print("検証: ok")
shutil.copy2(SETTINGS, BACKUP)
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=SETTINGS.parent, delete=False) as tmp:
    tmp.write(new_text)
shutil.copymode(SETTINGS, tmp.name)
Path(tmp.name).replace(SETTINGS)
print("設定の書き換え: changed")

try:
    port = PORT_FILE.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/reload", method="POST")
    with urllib.request.urlopen(req, timeout=60) as res:
        body = json.loads(res.read() or b"{}")
except Exception as exc:  # noqa: BLE001
    fail("設定の再読込", "POST /reload", exc)
unapplied = [str(item) for key in ("ignored", "dropped") for item in body.get(key) or []]
if any("rule_indexes" in item for item in unapplied):
    fail("設定の再読込", "POST /reload", json.dumps(body, ensure_ascii=False))
print("設定の再読込: changed")
if REMOVED in rule_indexes(SETTINGS.read_text(encoding="utf-8")):
    fail("反映の確認", f"yaml.safe_load({SETTINGS})", f"rule_indexes に {REMOVED} が残っています")
print("反映の確認: ok")
