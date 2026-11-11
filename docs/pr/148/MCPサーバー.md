# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/IF-122-2.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/interface/IF-122-2.py.yaml) | エントリの書き込み | フロー名・エラー名を変える 2 件と、エラー名を参照する `notes` |
| ドキュメント | [docs/interface/IF-122-6.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/interface/IF-122-6.py.yaml) | サーバーの起動 | フロー名・エラー名を変える 2 件 |
| ドキュメント | [docs/interface/IF-122-8.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/interface/IF-122-8.py.yaml) | ルールの検索 | フロー名を変える 2 件 |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/interface/IF-122-11.py.yaml) | 索引のチェック | フロー名を変える 3 件 |
| ドキュメント | [docs/interface/IF-122-13.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/interface/IF-122-13.py.yaml) | サーバーの状態の確認 | IF-122-6 のフロー名を参照する `notes` |
| ドキュメント | [docs/scenario/SC-122-19.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/scenario/SC-122-19.yaml) | 索引のエントリを編集する | 図のメッセージ 6 か所 |
| ドキュメント | [docs/scenario/SC-122-20.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d/docs/scenario/SC-122-20.yaml) | 索引をチェックする | 図のメッセージ 1 か所 |
| 実装 | [src/rule_inject/features/index/edit/service.py](https://github.com/shuhei1101/rule-inject/blob/b93a34d/src/rule_inject/features/index/edit/service.py) | 索引のエントリの編集 | 308 行目のエラーの文言と 299 行目のコメント |
| テスト | [tests/integration/server/test_server_start.py](https://github.com/shuhei1101/rule-inject/blob/b93a34d/tests/integration/server/test_server_start.py) | サーバーの起動の結合テスト | 71 行目の docstring |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| フロー名・エラー名 | 要件.md の表の新しい名前にする | 対応するシナリオは SC-122-4・12・18・19・20 |
| フロー名の参照 | IF-122-2 の `notes` と IF-122-13 の `notes` を新しい名前にする | - |
| 図のメッセージ | SC-122-19・20 を要件.md の表の新しい語句にする | 流れ・期待値は変えない |
| エラーの文言 | `IndexEditError` の `reason` を「書き込んだ後の索引がチェックに通らない」にする | 文言を照合するテストは無い |
| docstring | 要件.md の表の新しい語句にする | 処理は変えない |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `b93a34d..8ae5064` | - |

## テスト結果

（実装の工程で記入する）
