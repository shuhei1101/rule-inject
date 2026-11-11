# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [docs/interface/IF-122-6.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/docs/interface/IF-122-6.py.yaml) | サーバーの起動。制約 `instructions` が新しいファイルの作り方の決まりだけを定める | 制約 `instructions` と正常系の期待値に使い分けを追加 |
| ドキュメント | [docs/module/MOD-122-37.py.yaml](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/docs/module/MOD-122-37.py.yaml) | サーバーの組み立て。定数 `SERVER_INSTRUCTIONS` の値 | 値を新しい文面に修正 |
| ドキュメント | [docs/guide/コアコンセプト-MCPサーバー.md](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/docs/guide/%E3%82%B3%E3%82%A2%E3%82%B3%E3%83%B3%E3%82%BB%E3%83%97%E3%83%88-MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC.md) | instructions が届けるものを新しいファイルの作り方の決まりだけと説明している | 使い分けを追加 |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/src/rule_inject/server/app.py) | `SERVER_INSTRUCTIONS` とそのコメントが新しいファイルの作り方の決まりだけ | 文面とコメントを修正 |
| テスト | [tests/unit/rule_inject/server/test_app.py](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/tests/unit/rule_inject/server/test_app.py) | `test_build_server_instructions` が `Write`・`空の内容`・`Edit`・4,096 字以内を確認する | 使い分けの確認を追加 |
| テスト | [tests/integration/server/test_server_start.py](https://github.com/shuhei1101/rule-inject/blob/b93a34d97fbd19c696f1b7ebf902e75d4302bbe5/tests/integration/server/test_server_start.py) | `test_normal` が `initialize` の応答の `instructions` を確認する | 使い分けの確認を追加 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| instructions の文面 | 新しいファイルの作り方の決まりの後ろに、いつこの MCP を探すか・grep・Read との使い分け・ツール間の順序を事実の文で追加する。4,096 字以内 | 場面と順序の文面はインターフェース定義設計で確定する |
| 新しいファイルの作り方の決まり | 今の文面のまま | - |
| `initialize` の応答 | 接続のたびに同じ文面。設定ファイルでは変えられない | #133 から変わらない |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| インターフェース定義設計 | `9b08d0a..6423844` | IF-122-6 |
| インターフェース定義設計 | `800a005..2cc7a24` | レビューの指摘の修正 |
