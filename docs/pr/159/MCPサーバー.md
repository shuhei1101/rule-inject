# MCPサーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/scenario/SC-122-20.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/scenario/SC-122-20.yaml) | 索引をチェックする | 参加者と異常シナリオの名前が接続先を dev-docs と記載している |
| ドキュメント | [docs/scenario/SC-122-2.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/scenario/SC-122-2.yaml) | MCPサーバーの設定を再読込する | 読み込んだ値に「dev-docs の接続先」と記載している |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/interface/IF-122-11.py.yaml) | 索引のチェック | 偽の dev-docs・dev-docs に届かないフロー |
| ドキュメント | [docs/interface/IF-122-12.py.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/interface/IF-122-12.py.yaml) | 設定の再読込 | 応答の例の `dev_docs_url` が 8781 |
| ドキュメント | [docs/module/MOD-122-49.py.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-49.py.yaml) | 設定の読み込み | `DEFAULT_DEV_DOCS_URL` の値とテストの期待値が 8781 |
| ドキュメント | [docs/module/MOD-122-41.py.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-41.py.yaml)・[MOD-122-37](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-37.py.yaml)・[MOD-122-38](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-38.py.yaml)・[MOD-122-44](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-44.py.yaml) | 接続先のクライアント・チェックのツール | 接続先を dev-docs と記載している |
| ドキュメント | [docs/module/MOD-122-9.py.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-9.py.yaml)・[MOD-122-53](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/MOD-122-53.yaml) | タグのパターンの検出・サーバーの構成 | 接続先を dev-docs と記載している |
| ドキュメント | [docs/module/index.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/module/index.yaml)・[docs/test-procedure/TP-122-1.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/docs/test-procedure/TP-122-1.yaml)・[src/files.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/files.yaml) | モジュールの目次・テスト実行方法・コードの目録 | 接続先を dev-docs と記載している |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/server/app.py)・[check_tools.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/server/check_tools.py)・[types.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/server/types.py)・[features/index/check/tags.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/features/index/check/tags.py) | ツールの登録・チェックのツール・応答の型・タグのパターンの検出 | `reload_settings` の docstring（ツールの説明）とコメントが接続先を dev-docs と記載している |
| 実装 | [src/rule_inject/shared/settings.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/shared/settings.py) | `DEFAULT_DEV_DOCS_URL` | 既定値の書き換え |
| 実装 | [src/rule_inject/server/dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/src/rule_inject/server/dev_docs.py) | 使用中のタグを取得するクライアント | コメントと取得できなかった理由の文面 |
| 実装 | [settings.sample.yaml](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/settings.sample.yaml) | 設定ファイルの見本 | 既定値とコメント |
| テスト | [tests/unit/rule_inject/shared/test_settings.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/tests/unit/rule_inject/shared/test_settings.py)・[tests/unit/rule_inject/server/test_dev_docs.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/tests/unit/rule_inject/server/test_dev_docs.py) | 既定値を持つ単体テスト | 期待値の書き換え |
| テスト | [tests/integration/server/test_check_indexes.py](https://github.com/shuhei1101/rule-inject/blob/beabb2fddebe4fbbfc81e2156fa7eb9e3d921e8b/tests/integration/server/test_check_indexes.py) | 索引のチェックの結合テスト | 偽の接続先の呼び名 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 既定の接続先 | `DEFAULT_DEV_DOCS_URL` を `http://127.0.0.1:8786/mcp` にする | キー `dev_docs_url` は変えない |
| 呼び出すツール | `search_docs` の名前・引数（`source: "*"`・`group_by: "tags"`・`format: "json"`・`cwd`）は変えない | project-index#15 は文書の MCP のツールの名前・入力・出力を変えずに移した |
| 接続先の呼び名 | 要件のとおり、シナリオ・インターフェース定義・モジュール構成・取得できなかった理由の文面で、接続先を指す `dev-docs` を `project-index` にする | 識別子は変えない |
| 既存機能への影響 | 設定ファイルに `dev_docs_url` を記載していない端末は、更新したサーバーを再起動した後に 8786 へ問い合わせる | 記載している端末は記載した値を使用し続ける |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `beabb2f..7a75686` | - |
| インターフェース定義設計 | `5b69961..6e9403b` | 一体の非機能要件 NFR-122-1 と外部 API API-122-1 を含む |
| インターフェース定義設計 | `34155f2..0cab270` | レビューの指摘の修正（API-122-1 の project-index での動作確認） |

## テスト結果

なし
