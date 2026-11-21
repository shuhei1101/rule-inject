"""KNOWLEDGE_ROOT の追加の確認: 認証領域ごとに env を環境変数にして、フックと同じ索引の読み込みでこのリポジトリの rules.yaml を読む。"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import KEY, SETTINGS_FILES, VALUE  # noqa: E402

REPO = Path("/home/shuhei2441/repo/rule-inject/.claude/worktrees/develop")
LOAD = (
    "import sys;from rule_inject.features.index.service import load_indexes;"
    "r=load_indexes([sys.argv[1]], __import__('os').environ);"
    "[print(f'{f.path}: {f.reason}') for f in r.failures];sys.exit(1 if r.failures else 0)"
)

failed = False
for path in SETTINGS_FILES:
    env = json.loads(path.read_text(encoding="utf-8")).get("env", {})
    if env.get(KEY) != VALUE:
        print(f"{path} の {KEY}: failed（{env.get(KEY)}）")
        failed = True
        continue
    # フックの環境は settings.json の env を受け取る。ほかの環境変数を混ぜずに読み込む
    result = subprocess.run(
        [sys.executable, "-B", "-c", LOAD, str(REPO / "rules.yaml")],
        env={**{k: str(v) for k, v in env.items()}, "PYTHONPATH": str(REPO / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        print(f"{path} の索引の読み込み: ok")
    else:
        print(f"{path} の索引の読み込み: failed")
        print(result.stdout + result.stderr, file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
