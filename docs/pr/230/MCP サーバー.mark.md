# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| 実装 | [src/rule_inject/features/index/check/index.schema.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/index.schema.yaml) | 索引のスキーマ。エントリは `additionalProperties: false` | 名前を追加 |
| ドキュメント | [docs/interface/IF-122-2.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/IF-122-2.py.yaml) | `write_index_entry` | 引数に名前 |
| ドキュメント | [docs/interface/IF-122-7.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/IF-122-7.py.yaml) | `list_rules` | 応答に名前 |
| ドキュメント | [docs/interface/IF-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/IF-122-11.py.yaml)・[docs/interface/IF-122-24.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/interface/IF-122-24.py.yaml) | 索引のチェック・エントリの検査 | 名前を受け付ける |
| ドキュメント | [docs/module/MOD-122-11.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/MOD-122-11.py.yaml)・[MOD-122-12](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/MOD-122-12.py.yaml)・[MOD-122-43](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/MOD-122-43.py.yaml)・[MOD-122-44](https://github.com/shuhei1101/rule-inject/blob/develop/docs/module/MOD-122-44.py.yaml) | エントリの編集・ツール・応答の型 | 名前を追加 |
| 設定 | [rules.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/rules.yaml) | このリポジトリの索引 | 10 件に名前を記載 |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| スキーマ | エントリの `properties` に `minLength: 1` の文字列の名前を加える（必須にしない） | - |
| エントリの編集 | `write_index_entry` で名前を書き込み・外せる | - |
| 一覧 | `list_rules` のエントリに名前を返す（無ければ省く） | - |
| rules.yaml | ルールのファイル名から拡張子を除いた名前（例: `python-core-naming`）を記載する | 先頭で見分けられる |
| 反映 | プラグインは develop を自動で取り込むため、反映作業を作らない | - |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `b4fd083..4fe7822` | - |

## テスト結果

なし
