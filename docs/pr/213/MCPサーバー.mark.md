# MCPサーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/architecture/ARCH-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/architecture/ARCH-122-1.yaml) | サブシステムと外部システムの境界 | project-index から CLI を呼ぶ線と外部システムの行を追加 |
| ドキュメント | [docs/interface/IF-122-2.py.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/interface/IF-122-2.py.yaml) | エントリの書き込み（`write_index_entry`） | 書き込みのチェックを CLI と同じ判定にそろえる元 |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/interface/IF-122-11.py.yaml) | 索引のチェック（`check_indexes`） | 判定の共有元。変えない |
| ドキュメント | [docs/module/MOD-122-8.py.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/module/MOD-122-8.py.yaml) | 索引のチェックの service.py | CLI から呼ぶ判定の関数 |
| ドキュメント | [docs/module/MOD-122-54.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/module/MOD-122-54.yaml) | 索引のチェックのサブフィーチャーの構成 | CLI のファイルを追加 |
| ドキュメント | [docs/config/CFG-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/config/CFG-122-1.yaml) | 環境変数・索引のキー | CLI が参照する環境変数・引数があれば追加 |
| ドキュメント | [docs/layout/LAY-173-1.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/layout/LAY-173-1.yaml) | フォルダ構成 | CLI のファイルを追加 |
| ドキュメント | [docs/dev-command/CMD-183-1.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/docs/dev-command/CMD-183-1.yaml) | 開発コマンド | CLI を手元で実行するコマンドを追加 |
| 実装 | [src/rule_inject/features/index/check/service.py](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/src/rule_inject/features/index/check/service.py) | スキーマの検査と、書き込む前と後の問題の比較 | CLI から呼ぶ |
| 実装 | [src/rule_inject/features/index/check/index.schema.yaml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/src/rule_inject/features/index/check/index.schema.yaml) | 索引のスキーマ | 配信元の行の `schema` から指す |
| 実装 | [src/rule_inject/features/index/edit/service.py](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/src/rule_inject/features/index/edit/service.py) | エントリの書き込みと書き込みのチェック | 判定を CLI と共有する |
| 実装 | [pyproject.toml](https://github.com/shuhei1101/rule-inject/blob/78e19f57f4f54633c1954ffda46eb8ced351a55e/pyproject.toml) | パッケージの定義 | `[project.scripts]` が無い |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 検査の CLI | 標準入力のエントリ 1 件の YAML を、`write_index_entry` の書き込みのチェックと同じ判定（スキーマ・ルールの場所の実在）で検査し、違反を `validators[]` の出力の書式（`path`・`rule`・`fix` を持つ JSON の配列）で標準出力へ出す。合格は `[]` | `PROJECT_INDEX_VALIDATE_ON` が `delete` のときは合格を返却する |
| ルールの場所の基準 | エントリの `rule` の相対パスを、索引のファイルの場所から解決する。索引のファイルの場所は CLI の引数で受ける | `validators[].run` は配信元のフォルダで実行される |
| 判定の共有 | CLI と `write_index_entry` は同じ判定の関数を呼び、判定を 2 か所に持たない | - |
| 起動の方法 | 他のリポジトリから起動する方法を決め、公開ドキュメントに `project-index.yaml` の記載例を記載する | `未確定`（[要件](./要件.mark.md)） |
| スキーマ | 索引を配信する行の `schema` から、`records: rules` の要素をエントリとして検査できるスキーマを指せるようにする | `未確定`（[要件](./要件.mark.md)） |
| 既存機能への影響 | `write_index_entry`・`check_indexes` の入出力は変えない | - |

## テスト結果

### 単体

なし

### 結合

なし
