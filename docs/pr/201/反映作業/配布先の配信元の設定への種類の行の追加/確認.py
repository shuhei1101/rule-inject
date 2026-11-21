"""配布先の配信元の設定に、8 つの種類の行が knowledge のスキーマの参照で並ぶかを観測する。

使い方: python -B 確認.py [対象のリポジトリ]
"""

import sys
from pathlib import Path

import yaml

CONFIG_NAMES = ("project-index.yaml", "dev-docs.yaml")
# 引数の数の上限（スクリプト名と対象のリポジトリ）
MAX_ARGV = 2
KINDS = (
    "agent",
    "mcp_server",
    "launch",
    "agent_flow",
    "llm_call",
    "evaluation",
    "eval_criterion",
    "eval_case",
)


def main():
    if len(sys.argv) > MAX_ARGV:
        print("前提確認: failed")
        sys.exit(1)
    root = Path(sys.argv[1] if len(sys.argv) == MAX_ARGV else ".").resolve()
    config = next((root / n for n in CONFIG_NAMES if (root / n).is_file()), None)
    if config is None:
        print("配信元の設定: failed")
        sys.exit(1)
    documents = {
        d.get("id"): d
        for d in (yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("documents") or []
    }
    failed = False
    for kid in KINDS:
        schema = (documents.get(kid) or {}).get("schema")
        if isinstance(schema, dict) and schema.get("source") == "knowledge":
            print(f"{kid} の行: ok（{schema.get('ref')}）")
        else:
            print(f"{kid} の行: failed（{schema!r}）")
            failed = True
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
