# 配信元の設定に direct_commit を追加し、dev-docs の画面から直コミットしてよい種類を許可する

## 概要

利用者が dev-docs の画面から、このリポジトリの設計書とメタデータ（用語集・管理用の YAML・索引のエントリ）を直コミットで書き換えられるようにする。

## 背景

[#220](https://github.com/shuhei1101/rule-inject/issues/220) の要望。依頼元は [shuhei1101/dev-docs#314](https://github.com/shuhei1101/dev-docs/issues/314)（作業 PR [shuhei1101/dev-docs#317](https://github.com/shuhei1101/dev-docs/pull/317) のスコープ外の行）。
今の `project-index.yaml` には `direct_commit` が無く、dev-docs の画面では全ての種類が参照のみになる。
dev-docs 自身は [shuhei1101/dev-docs#317](https://github.com/shuhei1101/dev-docs/pull/317) で `direct_commit` を追加し、管理用の YAML の行を `body: false` で許可している。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [MCPサーバー](./MCPサーバー.mark.md) | MCP サーバーの計画書（配信元の設定への `direct_commit` の追加） |
| [反映作業](./反映作業/index.yaml) | 端末の設定の `write_api_kinds` への種類の登録 |
