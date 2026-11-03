"""各プロジェクトへ索引の参照するツールの記載を依頼する反映作業の、対象と Issue の文面と gh の呼び出し。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

# 依頼する Issue のタイトル（既に起票したかの判定にも使う）
ISSUE_TITLE = "索引のエントリに参照するツール（read_tool）を記載する"
# 依頼先: AI Monitor の監視対象のうち、rule-inject の索引（rules.yaml）を持つプロジェクトのリポジトリ。
# knowledge は shuhei1101/knowledge#158 で同じ見直しを扱うため含めない
TARGET_REPOS = (
    "shuhei1101/ai-monitor",
    "shuhei1101/aituber",
    "shuhei1101/gui-support",
    "shuhei1101/voice-paste",
    "shuhei1101/text-factory",
    "shuhei1101/image-factory",
    "shuhei1101/sound-factory",
    "shuhei1101/video-factory",
    "shuhei1101/asset-library",
    "shuhei1101/mindstella",
    "shuhei1101/observability",
    "shuhei1101/rule-inject",
    "shuhei1101/shuhdev-gateway",
)
ISSUE_BODY = """\
rule-inject の索引のエントリに、ルールを参照する MCP のツールと引数を記載できるようになりました（[rule-inject#102](https://github.com/shuhei1101/rule-inject/pull/102)）。
記載したルールは、案内でツールの名前と引数が載り、Claude Code がそのツールで必要な部分だけを参照します。
記載したツールと引数に一致する呼び出しは、結果の範囲によらずルールを既読にします。

## 依頼

このプロジェクトの索引（`rules.yaml`）のエントリのうち、dev-docs の配信元の文書を指すエントリに `read_tool` を記載してください。

```yaml
  - rule: ~/knowledge/docs/rule/python-core-naming.yaml
    paths: ["**/*.py"]
    read_tool:
      tool: mcp__plugin_dev-docs_dev-docs__search_docs
      args: '{"source": "knowledge", "filter": {"field": "id", "op": "eq", "values": ["python-core-naming"]}, "view": "full"}'
      optional_args: '{"sections": ["命名"]}'
```

- `args` には、どの文書を参照するかを決める引数（`source`・`filter`）を書きます。既読の判定に使います
- `optional_args` には、範囲を絞るだけの引数（`sections`・`fields`）を書きます。案内に「省略可」として載り、既読の判定には使いません
- 書き方は rule-inject の公開ドキュメント「索引の書式」の `read_tool` のセクションを参照してください
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Issue:
    """依頼の Issue 1 件（番号・状態）。"""

    number: int
    state: str


def run_gh(args: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """gh を引数の配列で呼ぶ（シェルを通さない）。"""
    return subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, check=False)


def find_issue(repo: str) -> Issue | None:
    """リポジトリにある依頼の Issue（タイトルが同じもの。状態は問わない）を返す。無ければ None。"""
    result = run_gh(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--search",
            f'"{ISSUE_TITLE}" in:title',
            "--json",
            "number,title,state",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    # 検索は部分一致のため、タイトルが完全に同じものだけを取る
    for item in json.loads(result.stdout):
        if item["title"] == ISSUE_TITLE:
            return Issue(number=item["number"], state=item["state"])
    return None
