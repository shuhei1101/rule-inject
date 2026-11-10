# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/app.py) | ツールの登録 | mypy が、ツールの関数を入れる変数の型の不一致を出す |
| 実装 | [src/rule_inject/features/index/check/service.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/features/index/check/service.py)・[src/rule_inject/server/check_tools.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/check_tools.py) | 索引のチェック | mypy が、`jsonschema` の型スタブが無い誤りを出す |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 型の誤りの修正（server/app.py） | ツールの関数を入れる変数の型を、登録する全てのツールの関数を受けられる型に修正する | ツールの登録と入出力は変えない |
| jsonschema の型スタブ | `pyproject.toml` の `dev` グループに `types-jsonschema` を追加する | 実行時の依存は変えない |

## テスト結果

### 単体

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| `tests/unit` 全体 | 全実行 | 実行のみ | ✅ | 373 テスト pass<br>`テスト結果/20261030054213_d3c25ce_単体テスト.log` |

### 結合

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| `tests/integration` 全体 | 全実行 | 実行のみ | ✅ | 135 テスト pass（`server/app.py` を触るため実行）<br>`テスト結果/20261030054213_d3c25ce_結合テスト.log` |
