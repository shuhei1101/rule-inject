# Rule Inject

Claude Code がファイルを触る前に、そのファイルに当たるルールをコンテキストへ案内するプラグイン。

## ドキュメント

実体は開発ドキュメント [dev/](./dev/) と公開ドキュメント [docs/](./docs/) にある。
使い方は [使い方](./docs/使い方/)。

着手前に索引を引いて読む。

```bash
PROJECT_ROOT="$PWD" PYTHONPATH="$AI_MONITOR_HOME/src" python3 -m ai_monitor.inject.build_docs_index
```
