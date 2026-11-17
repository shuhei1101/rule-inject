# mdmark の参照を既定で develop の最新にし、設定でバージョンを固定できるようにする

## 概要

rule-inject が mdmark を、既定では develop の最新で参照し、設定でタグか commit に固定できるようにする。

## 背景

[Issue #191](https://github.com/shuhei1101/rule-inject/issues/191) の要望。
mdmark の参照がタグに固定されていて、develop へ入った機能をタグが打たれるまで使えない。
mdmark の側は [shuhei1101/mdmark#620](https://github.com/shuhei1101/mdmark/issues/620) で、develop の最新の配布物の参照（jsDelivr の `@develop`・`npx github:shuhei1101/mdmark#develop`）と、設定の `version` の値 `develop` に対応した。
公開サイトのテーマは [AI Monitor v0.5.0 への追従（#193）](https://github.com/shuhei1101/rule-inject/pull/193) で、既定で develop の最新を読み、Pages の設定 `mdmark.version` で固定できる形になっている。

## 計画書

| ファイル | 中身 |
| --- | --- |
| [要件](./要件.md) | 要望の整理 |

## テスト結果

実装とテストコードを変えず、変更は mdmark の設定・Pages の設定・テスト実行方法だけのため、規約『V字モデル』の対応表で関係する単体・結合テストは無い。
lint 層の全件実行（mdmark check を含む）を流し、全ての検査が通った（`テスト結果/20261117105144_e79bcb0_lint.log`）。
