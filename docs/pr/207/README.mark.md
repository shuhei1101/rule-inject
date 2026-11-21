# rules.yaml の Python のルールを案内される状態にし、フックの注入文をプロンプトファイルへ移す

## 概要

このリポジトリで Python のファイルを触るときに knowledge の Python のルール 9 件が案内されるようにし、フックの注入文の本文をプロンプトファイルから読み込むようにする。

## 背景

束の親 [Issue #206](https://github.com/shuhei1101/rule-inject/issues/206) の要望で、子 [Issue #204](https://github.com/shuhei1101/rule-inject/issues/204) と [Issue #205](https://github.com/shuhei1101/rule-inject/issues/205) を 1 つの作業 PR で扱う。

- #204: [rules.yaml](https://github.com/shuhei1101/rule-inject/blob/8a74ccd/rules.yaml) は knowledge の Python のルール 9 件を `!{KNOWLEDGE_ROOT}/docs/rule/...` で指すが、端末に環境変数 `KNOWLEDGE_ROOT` が無く、フックが毎回「変数参照を展開できない」を出して 9 件を読み込めない。[PR #203](https://github.com/shuhei1101/rule-inject/pull/203) のコードはこの 9 件が案内されないまま作られ、レビューで規約違反を 2 件指摘された
- #205: knowledge の規約『プロンプトファイル』はフックの注入文（`kind: hook`）もプロンプトファイルに記載すると定めるが、フックは注入文を今もコードの定数に記載している。PR #203 で MCP サーバーの instructions とツールの description をプロンプトファイルへ移した際に、フックの注入文をスコープ外に残した

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.mark.md) | 要望の整理と変更箇所の由来 |
| [プラグイン](./プラグイン.mark.md) | プラグインの計画書 |
