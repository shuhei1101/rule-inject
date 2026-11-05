# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/サーバーの起動.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC%E3%81%AE%E8%B5%B7%E5%8B%95.py.yaml) | サーバーの起動 | 待ち受けのポートと登録の記述を修正する |
| ドキュメント | [設計書/モジュール構成/server/__main__.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/__main__.py.yaml) | 起動の入口 | ポートの解決を変えるときに修正する |
| 実装 | [src/rule_inject/server/__main__.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/__main__.py) | 起動の入口 | - |
| 実装 | `.mcp.json`（新規） | プラグインの MCP サーバーの接続先 | - |
| 実装 | [tests/e2e/単一ユースケース/test_run_resident_mcp_server.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/e2e/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/test_run_resident_mcp_server.py) | 「MCPサーバーを常駐させる」の E2E テスト | `claude mcp add` の登録を外す |
| 実装 | [tests/e2e/conftest.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/e2e/conftest.py) | E2E テストの共通設定 | `run_claude_cli` の用途を修正する |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 接続先 | プラグインのルート（リポジトリの直下）の `.mcp.json` に、キーを `rule-inject`、`type` を `http`、`url` を `http://127.0.0.1:${RULE_INJECT_PORT:-8783}/mcp` で記載する | `alwaysLoad` は付けない（毎ターン使うツールを持たない） |
| サーバーの待ち受け | `RULE_INJECT_PORT`、無ければ既定の `8783` で待ち受ける | `global.server_port` は廃止する |
| 起動していない端末 | Claude Code は接続の失敗を表示してセッションを続ける。フックの案内は今どおり動く | サーバーの起動は `global-setup` が担う |
| E2E | `--plugin-dir` のプラグインの `.mcp.json` で、登録せずに接続できることを確かめる | テストの空きポートは `RULE_INJECT_PORT` で渡す |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `9908014..63163d5` | - |
| 単一ユースケース設計 | `b9610ac..c81f7ed` | レビューの指摘の修正 |
| インターフェース定義設計 | `4946b60..ce0ba4d` | - |
| インターフェース定義設計 | `00eb45d..745f877` | レビューの指摘の修正 |

## テスト結果

未実施
