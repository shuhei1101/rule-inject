# hooks

Claude Code が呼ぶフックの入口と共通の実行処理の物理ファイルごとのモジュール

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [run.py](./run.py.yaml) | プラグインの直下の起動スクリプト。src/ を sys.path に追加して引数のフックを動かす |
| [__init__.py](./__init__.py.yaml) | フックのパッケージ |
| [_runner.py](./_runner.py.yaml) | 標準入出力・想定外の例外・ログ・設定ファイルの誤りのログの共通処理 |
| [rule_guide.py](./rule_guide.py.yaml) | ルール案内（PreToolUse） |
| [record_read.py](./record_read.py.yaml) | 既読の記録（PostToolUse） |
| [search_guide.py](./search_guide.py.yaml) | 検索結果の案内（PostToolUse） |
| [discard_read.py](./discard_read.py.yaml) | 既読の記録の破棄（PreCompact） |
| [sweep_read.py](./sweep_read.py.yaml) | 既読の記録の掃除（SessionStart） |
| [work_rules.py](./work_rules.py.yaml) | 作業の決まりの注入（SessionStart） |

<!-- /table -->
