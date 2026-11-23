"""端末の設定の rule-inject の行の `write_api_kinds` と配信の状態を読むだけで確かめる。"""

import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import HTTP_OK, KINDS, current_write_api_kinds, request, source_row  # noqa: E402

try:
    status, view = request("GET", "/settings/sources")
except RuntimeError as error:
    print("write_api_kinds の値: failed")
    print(error, file=sys.stderr)
    sys.exit(1)
row = source_row(view) if status == HTTP_OK else None
if row is None:
    print("write_api_kinds の値: failed")
    print(f"GET /settings/sources: HTTP {status}・rule-inject の行が無い")
    sys.exit(1)
kinds = current_write_api_kinds(row)
warnings = [w for w in view.get("warnings", []) if "rule-inject" in str(w.get("path", ""))]
failed = False
if kinds == KINDS:
    print("write_api_kinds の値: ok")
else:
    print("write_api_kinds の値: failed")
    print(f"観測した値: {kinds}")
    failed = True
if row.get("status") == "serving" and not row.get("errors") and not warnings:
    print("配信の状態: ok")
else:
    print("配信の状態: failed")
    print(f"status={row.get('status')} errors={row.get('errors')} warnings={warnings}")
    failed = True
sys.exit(1 if failed else 0)
