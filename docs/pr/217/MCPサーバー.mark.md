# MCPサーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| 設定 | [project-index.yaml](https://github.com/shuhei1101/rule-inject/blob/84a2320/project-index.yaml) | 配信元の設定 | 索引を配信する行と `validators` が無い。`rules.yaml` は `root` の行の 1 ファイルとしてだけ配信している |
| 索引 | [rules.yaml](https://github.com/shuhei1101/rule-inject/blob/84a2320/rules.yaml) | このリポジトリのルール索引 | 検査に合格するかは未確認 |
| スキーマ | [src/rule_inject/features/index/check/index.schema.yaml](https://github.com/shuhei1101/rule-inject/blob/84a2320/src/rule_inject/features/index/check/index.schema.yaml) | 索引のスキーマ | 含むタグがまだ無い |
| 実装 | [src/rule_inject/features/index/check/cli.py](https://github.com/shuhei1101/rule-inject/blob/84a2320/src/rule_inject/features/index/check/cli.py) | 検査のコマンド `rule-inject-validate-entry` | 変更しない |
| ドキュメント | [docs/guide/索引の書式.md](https://github.com/shuhei1101/rule-inject/blob/84a2320/docs/guide/%E7%B4%A2%E5%BC%95%E3%81%AE%E6%9B%B8%E5%BC%8F.md) | 「project-index の書き込みで検査する」の記載例 | 変更しない |
| シナリオ | [docs/scenario/SC-122-26.yaml](https://github.com/shuhei1101/rule-inject/blob/84a2320/docs/scenario/SC-122-26.yaml) | 書き込みの検査で索引のエントリを検査する | 変更しない |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 索引を配信する行 | `project-index.yaml` の `documents` に `id: rule_index`・`paths: [rules.yaml]`・`records: rules`・`validators: [rule_index_entry]` の行を追加する | `schema` の指し方は `未確定`（[要件](./要件.mark.md)） |
| 検査の行 | `project-index.yaml` の直下の `validators` に `id: rule_index_entry`・`run: [rule-inject-validate-entry, --index, rules.yaml]` を追加する。`on` は記載しない | 記載例は『索引の書式』のとおり |
| 今の索引の合格 | `rules.yaml` の全てのエントリを検査のコマンドへ 1 件ずつ指定し、出力が全て `[]` になることを確認する。違反があれば `rules.yaml` を修正する | 変数参照を展開できないエントリは違反にならない |
| 配信の確認 | 追加した後に `search_docs` を `source: rule-inject`・`kind: rule_index` で呼び、エントリが文書として返ることを確認する | - |
| 他のリポジトリへの起票 | 対象の各リポジトリの develop の `project-index.yaml` を確認し、持つリポジトリごとに `create_issue` で起票する。本文には索引のファイルのパス、記載例へのリンク、`ref` に rule-inject の次のリリースのタグを指すことと、事前に `global-setup` を再実行することを記載する | 起票した Issue の番号を `## 実装` に並べる |

## 実装

| 項目 | 内容 |
| --- | --- |
| `schema` の指し方 | [要件](./要件.mark.md) の推奨 A（リポジトリの中のパス）で記載した |
| 配信元の設定の検査 | project-index の `validate_source_config` で変更後の `project-index.yaml` を検査し、違反 0 件 |
| 今の索引の合格 | `rules.yaml` の 10 件のエントリを検査のコマンドへ 1 件ずつ指定し、全て `[]` |
| 配信の確認 | project-index は Git の配信元の設定を `default_ref`（develop）から参照するため、作業ブランチの `ref` では `rule_index` の文書は返らない（0 件）。マージの後に `search_docs`（`kind: rule_index`）で 10 件返ることを確認する |
| 起票した Issue | [shuhei1101/ai-monitor#3783](https://github.com/shuhei1101/ai-monitor/issues/3783)・[shuhei1101/alias-inject#143](https://github.com/shuhei1101/alias-inject/issues/143)・[shuhei1101/claude-balancer#368](https://github.com/shuhei1101/claude-balancer/issues/368)・[shuhei1101/dev-docs#320](https://github.com/shuhei1101/dev-docs/issues/320)・[shuhei1101/knowledge#565](https://github.com/shuhei1101/knowledge/issues/565)・[shuhei1101/mdmark#794](https://github.com/shuhei1101/mdmark/issues/794)・[shuhei1101/observability#123](https://github.com/shuhei1101/observability/issues/123)・[shuhei1101/project-index#270](https://github.com/shuhei1101/project-index/issues/270) |
| 起票しなかったリポジトリ | aituber・gui-support・mindstella・shuhdev-gateway・voice-paste（develop に `project-index.yaml` が無い） |

## テスト結果

### 単体

なし（コードを変えず、`project-index.yaml` の変更に対応する単体テストが無い）

### 結合

なし（コードを変えない。検査のコマンドの結合テストは [tests/integration/server/test_validate_entry.py](https://github.com/shuhei1101/rule-inject/blob/84a2320/tests/integration/server/test_validate_entry.py) が持つ）
