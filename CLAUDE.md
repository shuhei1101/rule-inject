# Rule Inject

Claude Code がファイルを触る前に、そのファイルに当たるルールをコンテキストへ案内するプラグイン。

## ドキュメント

実体は開発ドキュメント [dev/](./dev/) と公開ドキュメント [docs/](./docs/) にある。
使い方は [使い方](./docs/使い方/)。

着手前に索引を引いて読む。

```bash
PROJECT_ROOT="$PWD" PYTHONPATH="$AI_MONITOR_HOME/src" python3 -m ai_monitor.inject.build_docs_index
```

## 版

版を持つファイルは `version.ini`・`pyproject.toml`・`.claude-plugin/plugin.json` の 3 つ。
版上げでは 3 つを同じ値へ更新する（`version.ini` は先頭に `v` を付ける）。
