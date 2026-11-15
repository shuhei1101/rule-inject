# 文書のマーカーを mdmark の JSON の記載へ移す

## 概要

文書のマーカーの設定を、今の書き方（`キー=値`・`+機能`・位置の値）から mdmark の JSON の記載へ移す。

## 背景

[Issue #171](https://github.com/shuhei1101/rule-inject/issues/171) の要望。
mdmark の [shuhei1101/mdmark#477](https://github.com/shuhei1101/mdmark/pull/477) でマーカーの設定を JSON で記載できるようになり、今の書き方を参照する処理は [shuhei1101/mdmark#479](https://github.com/shuhei1101/mdmark/issues/479) で削除される。
依存の [shuhei1101/mdmark#528](https://github.com/shuhei1101/mdmark/issues/528)（v0.11.0 のタグ）と [shuhei1101/ai-monitor#3418](https://github.com/shuhei1101/ai-monitor/issues/3418)（`publish` が書き出すマーカーの JSON の記載への移行）は閉じている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |

## テスト結果

### 単体

なし。Markdown のマーカーと mdmark の設定だけを変え、コードを変えないため、規約『V字モデル』で対応する単体テストが無い。

### 結合

なし。単体と同じ理由で、対応する結合テストが無い。

### mdmark check

| 対象 | 結果 | 補足 |
| --- | --- | --- |
| `docs/guide/`（`docs/guide/mdmark.config.yaml`） | ✅ | `legacy_mark` 0 件。`plain_md_with_marks` だけが残る（スコープ外）<br>`テスト結果/20261116002629_fa83ed2_mdmark-check.log` |
| `docs/` の全ての Markdown（一時の設定で実行） | ✅ | `legacy_mark` 0 件。`map_unknown_*` は一時の設定が `map.kinds` を持たないためで、`docs/guide/` の設定では出ない<br>`テスト結果/20261116002629_fa83ed2_mdmark-check.log` |
