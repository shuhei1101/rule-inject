# mdmark check の plain_md_with_marks を解消する

## 概要

`mdmark check` が、記法を含む文書の拡張子が `.md` であることを指す `plain_md_with_marks` を出さないようにする。

## 背景

[Issue #188](https://github.com/shuhei1101/rule-inject/issues/188) の要望。
[#187](https://github.com/shuhei1101/rule-inject/pull/187) で文書のマーカーを mdmark v0.13.0 の JSON の記載へ移した後、`mdmark check` が記法を含む文書ごとに `plain_md_with_marks` を出す（[#187 の mdmark check のログ](https://github.com/shuhei1101/rule-inject/blob/develop/docs/pr/187/テスト結果/20261116002629_fa83ed2_mdmark-check.log)）。
#187 ではマーカーの移行と目的が違うため、スコープ外にした。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |

## テスト結果

### 単体

なし。mdmark の設定とフォルダ構成の設計書だけを変え、コードを変えないため、規約『V字モデル』で対応する単体テストが無い。

### 結合

なし。単体と同じ理由で、対応する結合テストが無い。

### mdmark check

| 対象 | 結果 | 補足 |
| --- | --- | --- |
| `docs/guide/`（`docs/guide/mdmark.config.yaml`） | ✅ | ずれ 0 件<br>`テスト結果/20261116011916_8068748_mdmark-check.log` |
| `docs/`（`docs/mdmark.config.yaml`） | ✅ | ずれ 0 件<br>`テスト結果/20261116011916_8068748_mdmark-check.log` |
