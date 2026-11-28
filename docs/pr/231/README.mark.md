# 設計書『テスト実行方法』の lint の全件実行で、.py を持たない反映作業のフォルダは mypy を実行しない

## 概要

planner・reviewer が設計書『テスト実行方法』の lint の全件のコマンドを実行したとき、Python のスクリプトを持たない反映作業のフォルダがあっても、違反が無ければ成功で終わるようになる。

## 背景

[Issue #229](https://github.com/shuhei1101/rule-inject/issues/229) の要望。作業 PR [#228](https://github.com/shuhei1101/rule-inject/pull/228) のマージ前の lint で検出した。

lint 層（TL-4）の全件のコマンドは反映作業のフォルダごとに `uv run mypy "$d"*.py` を実行する。
`.sh` と `dry-run.log` だけを持つ `docs/pr/217/反映作業/検査のコマンドの導入/` では glob が展開されず、mypy が `Cannot read file` で失敗し、どの作業 PR でも lint のログが失敗になる。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [プラグイン](./プラグイン.mark.md) | 設計書『テスト実行方法』の lint 層のコマンドの計画 |
