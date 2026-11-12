# Rule Inject

Claude Code がファイルを触る前に、そのファイルに該当するルールをコンテキストへ案内するプラグイン。

## ドキュメント

実体は [docs/](./docs/) にある。
使用方法は [使用方法](./docs/guide/使用方法.md)。

着手前に索引を検索して読む。

```bash
PROJECT_ROOT="$PWD" PYTHONPATH="$AI_MONITOR_HOME/src" python3 -m ai_monitor.inject.build_docs_index
```
