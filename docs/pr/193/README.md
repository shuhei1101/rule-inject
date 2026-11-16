# AI Monitor v0.5.0 の配布物へ追従する

## 概要

rule-inject が準拠する AI Monitor の配布物を v0.4.0 から v0.5.0 へ上げ、成果物を v0.5.0 のサイトのレイアウト・規約・テンプレートに合わせる。

## 背景

[Issue #192](https://github.com/shuhei1101/rule-inject/issues/192) の要望。
AI Monitor の v0.5.0 のタグで配布物が変わり、配布元が追従 Issue を起票した。
develop の `ai-monitor-version.ini` と `ai-monitor-theme.yaml` は `v0.4.0` のままになっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
| [反映作業](./反映作業/index.yaml) | 配布先の反映作業の一覧 |

## テスト結果

実装とテストコードを変えず、変更は版の控え・公開サイトのレイアウト・mdmark の設定だけのため、規約『V字モデル』の対応表で関係する単体・結合テストは無い。
`docs/mdmark.config.yaml` は、反映作業を一時的なクローンで流して設計書を生成し、`map.kinds` を記載する前は生成した設計書の図で `map_unknown_class` が出て、記載した後は出ないことを mdmark check で確かめた。
