"""端末の設定の rule-inject の行の `write_api_kinds` を空に戻す。"""

import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import HTTP_OK, SOURCE_ID, request  # noqa: E402

try:
    status, view = request("GET", "/settings/sources")
    if status != HTTP_OK:
        print("端末の設定の取得: failed")
        print(f"GET /settings/sources: HTTP {status}")
        sys.exit(1)
    body = {
        "expectedVersion": view["version"],
        "source": {"direct_commit": {"write_api_kinds": []}},
    }
    status, result = request("PATCH", f"/settings/sources/{SOURCE_ID}", body)
except RuntimeError as error:
    print("write_api_kinds の書き戻し: failed")
    print(error, file=sys.stderr)
    sys.exit(1)
if status != HTTP_OK:
    print("write_api_kinds の書き戻し: failed")
    print(f"PATCH /settings/sources/{SOURCE_ID}: HTTP {status} {result}")
    sys.exit(1)
print("write_api_kinds の書き戻し: changed")
