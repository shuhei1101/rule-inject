# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [dev/設計書/外部ライブラリ/mcp.yaml](https://github.com/shuhei1101/rule-inject/blob/60d73dbbd52d5a06f63381b64d890872cd7eb120/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E5%A4%96%E9%83%A8%E3%83%A9%E3%82%A4%E3%83%96%E3%83%A9%E3%83%AA/mcp.yaml) | MCP の公式の Python SDK | `used_in` の `tests/e2e/conftest.py` と、E2E の文書の MCP サーバーだけが使用するとする記述 |
| ドキュメント | [dev/設計書/外部ライブラリ/index.yaml](https://github.com/shuhei1101/rule-inject/blob/60d73dbbd52d5a06f63381b64d890872cd7eb120/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E5%A4%96%E9%83%A8%E3%83%A9%E3%82%A4%E3%83%96%E3%83%A9%E3%83%AA/index.yaml) | 外部ライブラリの目次 | mcp の行の概要に E2E テストの文書の MCP サーバー |
| テスト | [tests/e2e/](https://github.com/shuhei1101/rule-inject/tree/60d73dbbd52d5a06f63381b64d890872cd7eb120/tests/e2e) の MCP サーバーのテスト | 索引のチェック・編集・ルールの検索・効いているルールの一覧・既読の記録の確認と削除・設定の読み直し・再起動・常駐・状態の確認・更新と、2 つの複合ユースケース | 削除する（フォルダの削除はプラグインの計画書） |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 外部ライブラリ mcp | `used_in` から `tests/e2e/conftest.py` を削除し、E2E の文書の MCP サーバーだけが使用するとする文を削除する | `src/rule_inject/server` の使用は残る |
| 外部ライブラリの目次 | mcp の行の `summary` から E2E テストの文書の MCP サーバーを除外し、README を生成し直す | - |
| 依存 | `pyproject.toml` の `mcp` は残す | 常駐の MCP サーバーが使用する |

## テスト結果

なし
