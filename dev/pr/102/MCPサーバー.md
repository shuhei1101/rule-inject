# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/シナリオ/単一ユースケース/索引のエントリを編集する.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%82%A8%E3%83%B3%E3%83%88%E3%83%AA%E3%82%92%E7%B7%A8%E9%9B%86%E3%81%99%E3%82%8B.yaml) | 索引のエントリの新規作成・編集・削除 | 更新対象 |
| ドキュメント | [設計書/シナリオ/単一ユースケース/効いているルールの一覧を見る.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/%E5%8A%B9%E3%81%84%E3%81%A6%E3%81%84%E3%82%8B%E3%83%AB%E3%83%BC%E3%83%AB%E3%81%AE%E4%B8%80%E8%A6%A7%E3%82%92%E8%A6%8B%E3%82%8B.yaml) | 効いているエントリの一覧 | 更新対象 |
| ドキュメント | [設計書/シナリオ/単一ユースケース/索引をチェックする.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%B7%E3%83%8A%E3%83%AA%E3%82%AA/%E5%8D%98%E4%B8%80%E3%83%A6%E3%83%BC%E3%82%B9%E3%82%B1%E3%83%BC%E3%82%B9/%E7%B4%A2%E5%BC%95%E3%82%92%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF%E3%81%99%E3%82%8B.yaml) | 索引の JSON Schema への違反を返す | 更新対象 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/エントリの書き込み.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%A8%E3%83%B3%E3%83%88%E3%83%AA%E3%81%AE%E6%9B%B8%E3%81%8D%E8%BE%BC%E3%81%BF.py.yaml) | `entry` に書けるキーと書き込みの書式 | 更新対象 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/ルールの一覧.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%83%AB%E3%83%BC%E3%83%AB%E3%81%AE%E4%B8%80%E8%A6%A7.py.yaml) | `entries[]` のキー | 更新対象 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/索引のチェック.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E7%B4%A2%E5%BC%95%E3%81%AE%E3%83%81%E3%82%A7%E3%83%83%E3%82%AF.py.yaml) | 索引の JSON Schema への違反 | 更新対象 |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/ルールの検索.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%83%AB%E3%83%BC%E3%83%AB%E3%81%AE%E6%A4%9C%E7%B4%A2.py.yaml) | 当たるルールと止めるかを返す | 変えない（[要件](./要件.md) の `## スコープ外`） |
| ドキュメント | [設計書/モジュール構成/features/index/edit/_yaml.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/features/index/edit/_yaml.py.yaml) | 書き込む値の書式 | 更新対象 |
| ドキュメント | [設計書/モジュール構成/features/index/edit/service.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/features/index/edit/service.py.yaml) | `ENTRY_KEY_ORDER` | 更新対象 |
| ドキュメント | [設計書/モジュール構成/server/tools.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/tools.py.yaml) | 効いているエントリを応答にする `_rule_entry` | 更新対象 |
| ドキュメント | [設計書/モジュール構成/server/types.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/types.py.yaml) | `RuleEntry` | 更新対象 |
| 実装 | [src/rule_inject/features/index/check/index.schema.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/index.schema.yaml) | 索引の JSON Schema（エントリは `additionalProperties: false`） | キーの追加 |
| 実装 | [src/rule_inject/features/index/edit/_yaml.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/edit/_yaml.py) | 書き込む値の書式 | 新しいキーの書式の追加 |
| 実装 | [src/rule_inject/features/index/edit/service.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/edit/service.py) | `ENTRY_KEY_ORDER` | キーの追加 |
| 実装 | [src/rule_inject/server/tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/tools.py) | `_rule_entry` | 新しいキーを応答へ載せる |
| 実装 | [src/rule_inject/server/types.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/types.py) | `RuleEntry` | 新しいキーの属性の追加 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 索引の JSON Schema | 新しいキーを任意のプロパティとして追加し、ツールの完全名を必須にする | `read_tool` は `tool`（`^mcp__`）を必須、`args`（キーを 1 つ以上持つ JSON のオブジェクトの文字列）を任意とする |
| エントリの書き込み | `entry` に新しいキーを受け、`ENTRY_KEY_ORDER` の `read_by` の後ろの並びで書く | |
| ルールの一覧 | `entries[]` に新しいキーを索引に記載したまま載せる。記載の無いエントリでは `None` | インターフェース定義設計で `None` に確定 |
| ルールの検索 | 変えない | [要件](./要件.md) の `## スコープ外`。インターフェース定義設計のレビューで確定する |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `1c463d7..f155f05` | 索引のエントリを編集する・効いているルールの一覧を見る・索引をチェックする |
| インターフェース定義設計 | `f155f05..224ac19` | エントリの書き込み・ルールの一覧・索引のチェック |
| モジュール構成設計 | `224ac19..6d1d145` | エントリの編集（_yaml・service）・サーバー（tools・types） |

## テスト結果

未実施
