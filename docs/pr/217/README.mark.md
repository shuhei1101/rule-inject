# rule-inject の project-index.yaml で索引を配信して検査を追加し、他の配信元のリポジトリへ同じ追加の Issue を起票する

## 概要

rule-inject の `rules.yaml` を project-index で書き込むとき、`write_index_entry` と同じ検査に合格したエントリだけが書き込まれるようにする。
索引を持つ他の配信元のリポジトリへ、同じ追加の Issue を起票する。

## 背景

[#216](https://github.com/shuhei1101/rule-inject/issues/216) は [#214](https://github.com/shuhei1101/rule-inject/issues/214) と [#215](https://github.com/shuhei1101/rule-inject/issues/215) の束。
[#212](https://github.com/shuhei1101/rule-inject/issues/212)（作業 PR [#213](https://github.com/shuhei1101/rule-inject/pull/213)）で、索引のエントリ 1 件を検査するコマンド `rule-inject-validate-entry` と索引のスキーマを出した。
今の `project-index.yaml` には索引を配信する行が無く、`rules.yaml` は `root` の行の 1 ファイルとしてだけ配信されている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理 |
| [MCPサーバー](./MCPサーバー.mark.md) | MCP サーバーの計画書（索引を配信する行と検査の追加、他のリポジトリへの起票） |
| [反映作業](./反映作業/index.yaml) | 検査のコマンドの導入 |
