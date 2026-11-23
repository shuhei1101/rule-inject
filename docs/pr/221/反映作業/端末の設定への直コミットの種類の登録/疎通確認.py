"""端末の設定の API・端末の設定のファイル・配信元の設定に読み取りだけでつながるかを確かめる。"""

import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import HTTP_OK, SETTINGS_PATH, SOURCE_CONFIG_PATH, request, source_row  # noqa: E402

failed = False
try:
    status, view = request("GET", "/settings/sources")
    if status == HTTP_OK and source_row(view) is not None:
        print("端末の設定の API: ok")
    else:
        print("端末の設定の API: failed")
        print(f"GET /settings/sources: HTTP {status}・rule-inject の行が無い")
        failed = True
except RuntimeError as error:
    print("端末の設定の API: failed")
    print(error, file=sys.stderr)
    failed = True
for name, path in (("端末の設定のファイル", SETTINGS_PATH), ("配信元の設定", SOURCE_CONFIG_PATH)):
    if path.is_file():
        print(f"{name}: ok")
    else:
        print(f"{name}: failed")
        print(f"{path} が無い")
        failed = True
sys.exit(1 if failed else 0)
