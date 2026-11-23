"""端末の設定の rule-inject の行に `direct_commit.write_api_kinds` を登録する。"""

import shutil
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import (  # noqa: E402
    HTTP_OK,
    KINDS,
    SETTINGS_PATH,
    SOURCE_ID,
    config_kind_ids,
    current_write_api_kinds,
    request,
    set_write_api_kinds,
    source_row,
)

# 前提確認
args = sys.argv[1:]
if args not in ([], ["--dry-run"]):
    print("前提確認: failed")
    print(f"受け付けない引数: {args}")
    sys.exit(1)
dry_run = args == ["--dry-run"]
config_ids = config_kind_ids()
if sorted(config_ids) != sorted(KINDS):
    print("前提確認: failed")
    print(
        f"develop の project-index.yaml の direct_commit.kinds が登録する種類と違う: {config_ids}"
    )
    sys.exit(1)
try:
    status, view = request("GET", "/settings/sources")
except RuntimeError as error:
    print("前提確認: failed")
    print(error, file=sys.stderr)
    sys.exit(1)
row = source_row(view) if status == HTTP_OK else None
if row is None:
    print("前提確認: failed")
    print(f"GET /settings/sources: HTTP {status}・{SOURCE_ID} の行が無い")
    sys.exit(1)
print("前提確認: ok")

# 計画（--dry-run もここを通る）
before = current_write_api_kinds(row)
if before == KINDS:
    print("write_api_kinds の登録: skipped")
    sys.exit(0)
print(f"--- {SETTINGS_PATH} sources[id={SOURCE_ID}].direct_commit.write_api_kinds")
print(f"+++ {SETTINGS_PATH} sources[id={SOURCE_ID}].direct_commit.write_api_kinds")
for kind in before:
    print(f"-{kind}")
for kind in KINDS:
    print(f"+{kind}")
if dry_run:
    print("write_api_kinds の登録: changed")
    sys.exit(0)

# 適用（退避 → PATCH。検証と保存と再読み込みは PATCH が行う）
backup = SETTINGS_PATH.with_name(f"{SETTINGS_PATH.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}")
shutil.copy2(SETTINGS_PATH, backup)
print(f"退避: ok（{backup}）")
try:
    applied, detail = set_write_api_kinds(KINDS)
except RuntimeError as error:
    applied, detail = False, str(error)
if not applied:
    print("write_api_kinds の登録: failed")
    print(detail, file=sys.stderr)
    sys.exit(1)
print("write_api_kinds の登録: changed")
