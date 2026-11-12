# 公開ドキュメントの分類名・ページ名・URL「使い方」を「使用方法」へ置き換え、旧 URL から転送する

## 概要

公開ドキュメントの分類名・ページ名・`permalink` を「使い方」から「使用方法」へ置き換え、旧 URL `/使い方/` を開いた利用者を新 URL `/使用方法/` へ転送する。

## 背景

[Issue #153](https://github.com/shuhei1101/rule-inject/issues/153) の要望。
[PR #151](https://github.com/shuhei1101/rule-inject/pull/151)（[Issue #150](https://github.com/shuhei1101/rule-inject/issues/150)）は `docs/guide` の文中の AI slop の単語を置き換えたが、分類名・ページ名の「使い方」は公開済みの URL とサイドバーの構成が変わるため残した。
[PR #154](https://github.com/shuhei1101/rule-inject/pull/154)・[PR #156](https://github.com/shuhei1101/rule-inject/pull/156) も、分類名とページ名を指す箇所をこの Issue へ回した。
[確認事項](https://github.com/shuhei1101/rule-inject/issues/153#issuecomment-6799100530) へのユーザーの回答で、`permalink` も置き換えて旧 URL から転送する案 B に決まった。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |
