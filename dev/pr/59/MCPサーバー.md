# MCP サーバー

## 現状

<!-- table: data -->

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/アーキテクチャ図/アーキテクチャ図.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A2%E3%83%BC%E3%82%AD%E3%83%86%E3%82%AF%E3%83%81%E3%83%A3%E5%9B%B3/%E3%82%A2%E3%83%BC%E3%82%AD%E3%83%86%E3%82%AF%E3%83%81%E3%83%A3%E5%9B%B3.yaml) | サブシステムはプラグインだけで、制約に「常駐するサーバーは持たない」「フックは Python の標準ライブラリだけで書く」 | 常駐の MCP サーバーを全体図とサブシステム一覧へ追加し、制約を書き換える |
| ドキュメント | [設計書/非機能要件/非機能要件.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6/%E9%9D%9E%E6%A9%9F%E8%83%BD%E8%A6%81%E4%BB%B6.yaml) | フックの決定値 | 待ち受けのアドレス・既定のポート・編集を許す索引の範囲を追加する |
| ドキュメント | [設計書/外部ライブラリ/mcp.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E5%A4%96%E9%83%A8%E3%83%A9%E3%82%A4%E3%83%96%E3%83%A9%E3%83%AA/mcp.yaml) | E2E テストの文書の MCP サーバーを書く公式の Python SDK（開発時の依存） | サーバーの実行時の依存と、HTTP の待ち受けの API を追加する |
| ドキュメント | `設計書/外部ライブラリ/jsonschema.yaml`（新規） | - | 索引のチェックに使う `jsonschema` を追加する |
| ドキュメント | [設計書/テスト/テスト実行方法.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%86%E3%82%B9%E3%83%88/%E3%83%86%E3%82%B9%E3%83%88%E5%AE%9F%E8%A1%8C%E6%96%B9%E6%B3%95.yaml) | フックの単体・結合・E2E のテストの実行 | サーバーのテストの前提（依存の導入）を追加する |
| ドキュメント | `設計書/インターフェース定義/` の MCP サーバーのツール（新規） | - | サーバーの起動と、一覧・検索・チェック・編集のツールを追加する |
| ドキュメント | `設計書/モジュール構成/` の MCP サーバーのモジュール（新規） | - | サーバーの入口・ツール・索引の検証と書き込みを追加する |
| 実装 | `src/rule_inject/server/`（新規） | - | サーバーの入口とツールを追加する。Claude Code への HTTP の接続先は、利用者が `claude mcp add --transport http -s user` で設定ファイルのポートを指して登録し、セットアップに記載する |
| 実装 | [pyproject.toml](https://github.com/shuhei1101/rule-inject/blob/develop/pyproject.toml) | `dependencies` は空で、`mcp` は開発時の依存 | サーバーの依存（`mcp`・`jsonschema`・`ruamel.yaml`）を任意の依存 `server` と `dev` グループに追加する。フックは読まない |
| 実装 | `tests/unit`・`tests/integration`・`tests/e2e` のサーバーのテスト（新規） | - | 追加する |

<!-- /table -->

## 変更方針

<!-- table: data -->

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| サーバーの置き場所 | フックと同じリポジトリの `src/rule_inject/server/` に置き、ローカルのクローンから起動する | 起動と停止の方法は `要件.md` の `## 要望` |
| プロジェクトの解決 | 一覧・検索のツールはプロジェクトの直下のパスを引数で受け、フックの `CLAUDE_PROJECT_DIR` と同じ規則で `projects[].match` を当てる | サーバーはセッションを持たないため |
| 照合 | 検索のツールは `features/index` の照合をそのまま使い、フックと同じ結果を返す。既読の記録は見ない | 止めるかは未読とみなしたときの結果 |
| 環境変数 | サーバーは Claude Code の外で起動するため、フックが Claude Code の設定の `env` で受け取る環境変数（`RULE_INJECT_CONFIG`・索引の `!{名前}` の変数・`XDG_CONFIG_HOME`・`XDG_STATE_HOME`）を、起動の側にも置く前提にする | 使い方と `docs/リファレンス/環境変数.md` に記載する。一覧・チェックのツールの応答に、サーバーが読んだ設定ファイルの場所を載せる |
| 索引のスキーマ | 索引のキーと値の範囲を JSON Schema（YAML）で持ち、チェックと編集の検証に使う。チェックと編集の書き込み前の検証は、まずフックと同じ `parse_index`（`load_indexes`）で読み、読めたときだけ JSON Schema に照らす | 索引の書式（`docs/リファレンス/索引の書式.md`）と食い違わないことをテストで確かめる。スキーマの範囲とフックのパーサーが受け付ける範囲が食い違わないこともテストで確かめる |
| 編集の範囲 | 編集のツールが書き込めるのは、設定ファイルで読む索引に限る | 任意のファイルへの書き込みを防ぐ |
| Claude Code への登録 | プラグインに `.mcp.json` を置かず、利用者が `claude mcp add --transport http -s user` で設定ファイルのポートを指して登録する | コーディング規約『MCP』の `## 登録` はプラグインの `.mcp.json` に `${RULE_INJECT_PORT:-8783}` の `url` を記載するが、要望のとおり設定ファイルの `global.server_port` でポートを変えると接続先とずれるため |

<!-- /table -->

## PoC 結果

<!-- table: data -->

| 検証構成 | 成功条件 | 結果 | PoC PR | 補足 |
| --- | --- | --- | --- | --- |
| `mcp` 2.2.0 の Streamable HTTP | 127.0.0.1 だけで待ち受ける | ✅ `127.0.0.1:60808` だけ | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | `ss -ltn` で確認 |
| Claude Code 2.1.312 からの呼び出し | `claude -p --mcp-config` からツールを呼び、`permission_denials` が空で戻り値が出る | ✅ `poc-echo:hello` | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | 長期トークンを `claude-balancer exec --client ai-monitor --kind short` で借りて実行。`claude mcp add --transport http -s user` で登録した状態の `claude mcp list` も `✔ Connected` |
| サーバーを止めた状態 | `claude -p` が応答する | ✅ `ok` を返し終了コード 0 | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | `claude mcp list` は `✘ Failed to connect — ECONNREFUSED` |
| `ruamel.yaml` 0.19.1 の round-trip | 1 行のフロー形式のリストに 80 字を超える値を追加しても 1 行のまま、差分が書き換えた行だけ | ✅ 差分 3 行 | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | 書き換えた 1 行と、追加したエントリの 2 行 |
| round-trip の後のフックの読み取り | `load_indexes` が読み飛ばし 0・読めない索引 0 で、追加した値が照合で当たる | ✅ 0 件・0 件 | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | 追加したエントリ（空白入りの長い `rule`）も当たる |
| `jsonschema` 4.26.0 | 型違反・許さないキー・必須キーの欠けを、場所と理由つきで返す | ✅ 3 種類 | [#60](https://github.com/shuhei1101/rule-inject/pull/60)（closed） | 例 `type ['rules', 0, 'paths'] 'src/**/*.py' is not of type 'array'` |

<!-- /table -->

結論: 成立。
常駐の HTTP の MCP サーバーは Claude Code から登録して呼べ、止まっていても Claude Code は動く。
`ruamel.yaml` は既定の設定では `parse_index` が読めない書式で書き戻すため、次の設定で使う。

```python
yaml = YAML()
yaml.width = 4096
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.preserve_quotes = True

data = yaml.load(text)
data["rules"][0]["paths"].append(long_path)  # 既存のフロー形式のリストは 1 行のまま
entry = CommentedMap(rule=new_rule)
paths = CommentedSeq([new_path])
paths.fa.set_flow_style()  # 新しいリストはフロー形式を指定しないとブロック形式になる
entry["paths"] = paths
data["rules"].append(entry)
yaml.dump(data, out)
```

`*` を含む値は `ruamel.yaml` が単一引用符で囲んで書き出し、`parse_index` はそのまま読める。
diff の見どころは `poc/roundtrip.py`（書き戻しと `load_indexes`）と `poc/server.py`（`run("streamable-http", host="127.0.0.1", port=...)`）。

## テスト結果

### 単体

| ファイル | メソッド | 変更種別 | 結果 | 補足 |
| --- | --- | --- | --- | --- |
| `tests/unit/rule_inject/features/index/check/test_service.py` | 全実行 | 新規 | ✅ | 11 テスト pass |
| `tests/unit/rule_inject/features/index/edit/test_service.py` | 全実行 | 新規 | ✅ | 30 テスト pass |
| `tests/unit/rule_inject/features/index/edit/test_types.py` | 全実行 | 新規 | ✅ | 1 テスト pass |
| `tests/unit/rule_inject/features/index/edit/test_yaml.py` | 全実行 | 新規 | ✅ | 2 テスト pass |
| `tests/unit/rule_inject/server/test_app.py` | 全実行 | 新規 | ✅ | 1 テスト pass |
| `tests/unit/rule_inject/server/test_format.py` | 全実行 | 新規 | ✅ | 4 テスト pass |
| `tests/unit/rule_inject/server/test_main.py` | 全実行 | 新規 | ✅ | 2 テスト pass |
| `tests/unit/rule_inject/server/test_tools.py` | 全実行 | 新規 | ✅ | 14 テスト pass<br>`tests/unit` 全体 345 テストの実行は `テスト結果/20261028211628_f977d10_単体テスト.log` |
