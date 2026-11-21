"""KNOWLEDGE_ROOT の追加: エージェントの認証領域ごとの settings.json の env に KNOWLEDGE_ROOT を入れる。"""

import difflib
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import KEY, SETTINGS_FILES, VALUE  # noqa: E402

# 前提確認（全ての対象を読めてから書き換える）
args = sys.argv[1:]
if len(args) > 1 or (args and args[0] != "--dry-run"):
    print("前提確認: failed")
    print(f"unexpected arguments: {args}", file=sys.stderr)
    sys.exit(1)
dry_run = args == ["--dry-run"]
loaded: list[tuple[Path, str, dict]] = []
for path in SETTINGS_FILES:
    try:
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
    except (OSError, ValueError) as exc:
        print("前提確認: failed")
        print(f"read {path}: {exc}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict) or not isinstance(data.get("env"), dict):
        print("前提確認: failed")
        print(f"{path}: 最上位か env がオブジェクトでない", file=sys.stderr)
        sys.exit(1)
    loaded.append((path, original, data))
if not Path(VALUE).is_dir():
    print("前提確認: failed")
    print(f"knowledge のクローンが無い: {VALUE}", file=sys.stderr)
    sys.exit(1)
print("前提確認: ok")

# 計画（--dry-run もここを通る）
plans: list[tuple[Path, str]] = []
for path, original, data in loaded:
    if data["env"].get(KEY) == VALUE:
        print(f"{path}: skipped")
        continue
    data["env"][KEY] = VALUE
    updated = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.writelines(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
    plans.append((path, updated))
    if dry_run:
        print(f"{path}: changed")
if dry_run or not plans:
    sys.exit(0)

# 適用（対象ごとに一時ファイル → 検証 → 退避 → 置き換え）
stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
for path, updated in plans:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(updated)
        new = Path(tmp.name)
    if json.loads(new.read_text(encoding="utf-8")).get("env", {}).get(KEY) != VALUE:
        new.unlink()
        print(f"{path} の検証: failed")
        sys.exit(1)
    backup = path.with_name(f"{path.name}.bak-{stamp}")
    shutil.copy2(path, backup)
    new.replace(path)
    print(f"{path}: changed（退避: {backup.name}）")
