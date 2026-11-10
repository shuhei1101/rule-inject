# 今ある E2E のテストと、E2E だけが使う部品を develop から削除する

## 概要

develop から、今ある E2E のテストと、E2E だけが使用する部品を削除する。

## 背景

[Issue #118](https://github.com/shuhei1101/rule-inject/issues/118) の要望。
0.x の間は E2E を実行せず修正もしないと決まり、今ある E2E は仕様の変更で古くなって、エージェントが参照して誤解するノイズになっている。
E2E はメジャーのリリースの前に、全体の仕様が固まった状態でまとめて作り直す。
関係する Issue は [shuhei1101/ai-monitor#3317](https://github.com/shuhei1101/ai-monitor/issues/3317)（0.x の間は E2E を master へ入れるときだけ実行する）と [#53](https://github.com/shuhei1101/rule-inject/issues/53)（Sprint v0.2.4 の E2E 実行）。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理と終わりの条件 |
| [プラグイン](./プラグイン.md) | E2E のテストの削除と、テスト実行方法・インターフェース定義・claude-code の記述の修正 |
| [MCP サーバー](./MCPサーバー.md) | 外部ライブラリ mcp の E2E の記述の修正 |