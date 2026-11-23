"""端末の設定の rule-inject の行の `write_api_kinds` を空に戻す。"""

import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from common import set_write_api_kinds  # noqa: E402

try:
    applied, detail = set_write_api_kinds([])
except RuntimeError as error:
    applied, detail = False, str(error)
if not applied:
    print("write_api_kinds の書き戻し: failed")
    print(detail, file=sys.stderr)
    sys.exit(1)
print("write_api_kinds の書き戻し: changed")
