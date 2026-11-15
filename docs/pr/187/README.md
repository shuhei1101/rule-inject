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
