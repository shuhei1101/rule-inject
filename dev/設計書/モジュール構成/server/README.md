# server

常駐の MCP サーバーの起動・ツール・応答の形式の物理ファイルごとのモジュール

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [__main__.py](./__main__.py.yaml) | 起動の入口 |
| [app.py](./app.py.yaml) | コンポジションルートとツールの登録 |
| [tools.py](./tools.py.yaml) | ルールの一覧・検索・エントリの書き込み・削除のツール |
| [check_tools.py](./check_tools.py.yaml) | 索引のチェックのツールと続きの位置の変換 |
| [dev_docs.py](./dev_docs.py.yaml) | dev-docs から使われているタグを引くクライアント |
| [record_tools.py](./record_tools.py.yaml) | 既読の記録の確認・削除のツール |
| [types.py](./types.py.yaml) | 応答の形式の種類と応答のモデル |
| [_format.py](./_format.py.yaml) | 応答の形式と長さの切り詰め |

<!-- /table -->
