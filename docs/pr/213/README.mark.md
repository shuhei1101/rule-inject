# 索引の検査を project-index の validators[] から呼べる CLI とスキーマとして出す

## 概要

索引を配信する配信元で、project-index の書き込みが、rule-inject の索引の検査に合格したエントリだけを書き込めるようにする。

## 背景

[shuhei1101/rule-inject#212](https://github.com/shuhei1101/rule-inject/issues/212) の要望。
[shuhei1101/dev-docs#313](https://github.com/shuhei1101/dev-docs/pull/313) で dev-docs のメタデータの画面に「rule-inject の索引」のタブを作ったが、project-index の書き込みの API は行の `schema` と `validators[]` だけで検査するため、`write_index_entry` と同じ検査を実行する手段が無く、索引の直コミットはスコープ外になった。
[shuhei1101/dev-docs#316](https://github.com/shuhei1101/dev-docs/issues/316) の[判断](https://github.com/shuhei1101/dev-docs/issues/316#issuecomment-7088525956)で、このリポジトリで検査の CLI とスキーマを出すと決めた。
[shuhei1101/project-index#258](https://github.com/shuhei1101/project-index/issues/258)（project-index が文書でないファイルとして索引を扱う案）とは、[扱いの判断](https://github.com/shuhei1101/rule-inject/issues/212#issuecomment-7088633660)で、検査の持ち主を rule-inject に保つこちらの案を採った。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [MCPサーバー](./MCPサーバー.mark.md) | MCP サーバーの計画書（索引の検査の CLI とスキーマ） |
