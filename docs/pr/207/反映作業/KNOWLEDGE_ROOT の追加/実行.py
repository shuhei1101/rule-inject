"""KNOWLEDGE_ROOT の追加: ~/.claude/settings.json の env に KNOWLEDGE_ROOT を入れる。"""

import difflib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SETTINGS = Path("/home/shuhei2441/.claude/settings.json")
KEY = "KNOWLEDGE_ROOT"
VALUE = "/home/shuhei2441/repo/knowledge/.claude/worktrees/develop"

# 前提確認
args = sys.argv[1:]
if len(args) > 1 or (args and args[0] != "--dry-run"):
    print("前提確認: failed")
    print(f"unexpected arguments: {args}", file=sys.stderr)
    sys.exit(1)
dry_run = args == ["--dry-run"]
try:
    original = SETTINGS.read_text(encoding="utf-8")
    data = json.loads(original)
except (OSError, ValueError) as exc:
    print("前提確認: failed")
    print(f"read {SETTINGS}: {exc}", file=sys.stderr)
    sys.exit(1)
env = data.get("env")
if not isinstance(data, dict) or not isinstance(env, dict) or not Path(VALUE).is_dir():
    print("前提確認: failed")
    print("settings.json に env のオブジェクトが無いか、knowledge のクローンが無い", file=sys.stderr)
    sys.exit(1)
print("前提確認: ok")

# 計画（--dry-run もここを通る）
if env.get(KEY) == VALUE:
    print("env の書き換え: skipped")
    sys.exit(0)
env[KEY] = VALUE
updated = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
sys.stdout.writelines(
    difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=str(SETTINGS),
        tofile=str(SETTINGS),
    )
)
if dry_run:
    print("env の書き換え: changed")
    sys.exit(0)

# 適用（一時ファイル → 検証 → 退避 → 置き換え）
with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=SETTINGS.parent, delete=False) as tmp:
    tmp.write(updated)
    new = Path(tmp.name)
try:
    if json.loads(new.read_text(encoding="utf-8")).get("env", {}).get(KEY) != VALUE:
        raise ValueError("書き込んだ env に KNOWLEDGE_ROOT が無い")
except ValueError as exc:
    new.unlink()
    print("検証: failed")
    print(str(exc), file=sys.stderr)
    sys.exit(1)
print("検証: ok")
backup = SETTINGS.with_name(f"{SETTINGS.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
shutil.copy2(SETTINGS, backup)
print(f"退避: ok（{backup}）")
new.replace(SETTINGS)
print("env の書き換え: changed")
