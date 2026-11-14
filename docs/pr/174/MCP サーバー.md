# MCP サーバー

## 現状

<!-- table: data -->

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/IF-122-1.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-1.py.yaml) | `delete_index_entry` | `sequenceDiagram` 10 件 |
| ドキュメント | [docs/interface/IF-122-2.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-2.py.yaml) | `write_index_entry` | `sequenceDiagram` 14 件 |
| ドキュメント | [docs/interface/IF-122-6.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-6.py.yaml) | 待ち受けと SIGTERM での停止 | `sequenceDiagram` 5 件 |
| ドキュメント | [docs/interface/IF-122-7.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-7.py.yaml) | `list_rules` | `sequenceDiagram` 6 件 |
| ドキュメント | [docs/interface/IF-122-8.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-8.py.yaml) | `search_rules` | `sequenceDiagram` 5 件 |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/interface/IF-122-11.py.yaml) | `check_indexes` | `sequenceDiagram` 8 件 |
| ドキュメント | [docs/scenario/SC-122-6.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/scenario/SC-122-6.yaml) | 接続時の instructions の受け取り | `sequenceDiagram` |
| ドキュメント | [docs/scenario/SC-122-25.yaml](https://github.com/shuhei1101/rule-inject/blob/c10f84d/docs/scenario/SC-122-25.yaml) | 索引のエントリを修正して次の案内で有効にする流れ（複合ユースケース） | `flowchart TD` |

<!-- /table -->

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| `flow` の図 | 各 ```` ```mermaid ```` のコードブロックを `<!-- map -->` と `<!-- /map -->` で囲む。コードブロックの中身は変えない | 補足 `<!-- map-data -->` は配置しない |
| 検査 | 計画書『[プラグイン](./プラグイン.md)』の検査と同じ | - |
