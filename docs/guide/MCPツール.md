# MCPツール

常駐の MCP サーバーが持つツールの引数と応答

サーバーの役割は [MCPサーバー](コアコンセプト-MCPサーバー.md)、起動の手順は [セットアップ](セットアップ.md)。
接続先は `http://127.0.0.1:{ポート}/mcp`。

## 共通

`get_read_records`・`delete_read_records` と管理のツール（`get_server_status`・`reload_settings`・`restart_server`・`update_server`）以外の全てのツールが `project_dir` を受ける。`reload_settings` は `project_dir` を省いてもよい。
フックの `CLAUDE_PROJECT_DIR` に該当する値で、`projects[].match` を適用して索引を決め、`projects[].indexes` の相対パスを解く（[設定ファイル](設定ファイル.md)）。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `project_dir` | 文字列 | ✅ | - | プロジェクトの直下。絶対パス |
| `format` | `markdown` / `json` | - | `markdown` | 応答の形式。`json` は structuredContent と text に同じ JSON を入れる。`markdown` は同じ項目を Markdown の表で text に入れる |

`format` は編集のツールと `delete_read_records` と管理のツールにはない。

次のときは、ツールの結果が `isError: true` になり、text に理由が入る。

- `project_dir` が絶対パスでない
- 呼び出しの時点で設定ファイルが読めない（場所と理由を返却する。既定値では動かさない）
- 再起動か更新の再起動を始めた後で、まだ待ち受けを閉じていない（`get_server_status` だけは受け付ける）

読む索引と `rule` の変数参照は、フックと同じ規則で決まる。
変数参照は、サーバーを起動した環境の環境変数で展開する。

## list_rules

プロジェクトで読む索引と、有効なエントリを返却する。
読めない索引・読み飛ばしたエントリ・無効のエントリは、エラーにせず理由とともに返却する。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `limit` | 整数 | - | `100` | 返却する有効なエントリの件数の上限。1〜500 |
| `cursor` | 文字列 | - | 先頭から返却する | 前の応答の `next_cursor` |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 一覧を作れたか。読めない索引があっても `true` |
| `output` | 文字列 | 索引の数と各一覧の件数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所。設定ファイルを読まなかったとき（`RULE_INJECT_CONFIG` が無く、既定のパスにファイルも無いとき）は `null` |
| `indexes` | 文字列のリスト | 読む索引の場所。フックが読む順 |
| `entries[]` | オブジェクトのリスト | 有効なエントリ。`index`・`position`・`rev`・`rule`・`paths`・`exclude`・`tools`・`args`・`on`・`read_by`・`read_tool`（記載が無いエントリは `null`） |
| `unreadable_indexes[]` | オブジェクトのリスト | 読めない索引の `index` と `reason` |
| `skipped_entries[]` | オブジェクトのリスト | 読み飛ばしたエントリの `index`・`position`・`rev`・`rule`・`reason` |
| `disabled_entries[]` | オブジェクトのリスト | `enabled: false` のエントリの `index`・`position`・`rev`・`rule` |
| `total` | 整数 | 有効なエントリの総数 |
| `next_cursor` | 文字列 / `null` | 続きを取るときに `cursor` へ指定する値。続きが無いときは `null` |

<!-- /table -->

- `position` は索引の `rules` の中の位置（0 始まり）で、編集のツールの `position` に指定する
- `rev` はエントリのバージョンで、編集のツールの `expected_rev` に指定する。エントリのキーと値をキーの順に並べた JSON の SHA-256 の先頭 12 文字で、コメント・引用符・字下げだけの違いでは変わらない
- `entries[].on` は、エントリが `on` を記載しないときは索引の `default_on` を埋めた値
- 応答が長さの上限を超えるときは、その手前で切って `next_cursor` を返却する。読めない索引・読み飛ばしたエントリ・無効のエントリは先頭のページだけに載る

## search_rules

ファイルのパスと操作の種別か MCP のツールの呼び出しを受け、フックと同じ照合でヒットするルールを返却する。
既読の記録は確認せず、全て未読とみなした結果を返却する。
`enabled: false` のエントリは照合に使用しない。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `path` | 文字列 | - | ツールの呼び出しで検索する | 操作の対象のファイルの絶対パス。まだ無いパスも受ける。`tool_name` とどちらか 1 つだけ |
| `operation` | `read` / `write` | - | なし | パスへの操作の種別。`path` を指定するときは必須。`read` は Read・Grep・Bash の読み取り、`write` は Edit・Write・NotebookEdit |
| `tool_name` | 文字列 | - | パスで検索する | MCP のツールの完全名。`mcp__` で始まる。`path` とどちらか 1 つだけ。`mcp` として照合する |
| `arguments` | オブジェクト | - | 引数を持たない呼び出しとして照合する | MCP のツールの引数。`tool_name` を指定するときだけ使用し、エントリの `args` と照合する |

次の指定方法は `isError: true` になる。

- `path` と `tool_name` の両方を指定する・どちらも指定しない
- `path` を指定して `operation` を指定しない
- `path` が絶対パスでない

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 照合できたか。ヒットするルールが無くても `true` |
| `output` | 文字列 | ヒットしたルールの件数と、止めるルールの件数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所 |
| `operation` | `read` / `write` / `mcp` | 照合に使用した操作の種別 |
| `matched[].rule` | 文字列 | ヒットしたルールの場所。同じ場所にヒットしたエントリは 1 件にまとめる |
| `matched[].blocking` | 真偽値 | 未読のときに操作を止めるか。ヒットしたエントリのどれか 1 つでも `operation` が `on` に入っていれば `true` |
| `matched[].entries[]` | オブジェクトのリスト | ヒットしたエントリの `index` と `position` |
| `unreadable_indexes[]` | オブジェクトのリスト | `list_rules` と同じ |
| `skipped_entries[]` | オブジェクトのリスト | `list_rules` と同じ |

<!-- /table -->

## check_indexes

プロジェクトで読む索引ごとに、フックが読めない理由・JSON Schema への違反・`rule` の場所にファイルが無いエントリ・`paths` がプロジェクトのどのファイルにもヒットしないエントリ・dev-docs の使用中のどのタグにもヒットしないタグのパターンを返却する。
索引の問題はエラーにせず応答に記載する。

索引ごとに、フックと同じ読み取り、JSON Schema、`rule` の場所の実在の順に確認する。
フックが読めない索引は、JSON Schema に照らさず、`rule` の場所も確認しない（読めない理由だけを返却する）。
JSON Schema の場所は [索引の書式](索引の書式.md)。

`project_dir`・`format` のほかに、次の引数を受ける。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `include_global` | 真偽値 | - | `false` | ユーザー全体の索引（`global.indexes`、無ければユーザーの既定の索引）の `paths` のヒットしないエントリも確認するか |
| `cursor` | 文字列 | - | 最初のファイルから辿る | 前の応答の `unmatched_scan.next_cursor`。`paths` のヒットしないエントリの検出を、前の呼び出しが止まった続きから行う |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | チェックを最後まで行えたか。問題が見つかっても `true` |
| `output` | 文字列 | チェックした索引の数と問題の件数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所 |
| `problem_count` | 整数 | 全ての索引の `hook_error`・`violations`・`missing_rules`・`skipped_entries` の件数と、`origin` が `project` の索引の `unmatched_paths` の件数の合計。`origin` が `global` の索引の `unmatched_paths` と、どの索引の `unused_tag_patterns` も数えない |
| `unmatched_scan.completed` | 真偽値 | `paths` のヒットしないエントリの検出を最後まで行えたか。`false` のときはどの索引の `unmatched_paths` も空 |
| `unmatched_scan.scanned_files` | 整数 | 辿ったプロジェクトのファイルの数。`cursor` を指定したときは、最初の呼び出しからの合計 |
| `unmatched_scan.reason` | 文字列 / `null` | 検出を終えられなかった理由。辿る時間の上限の秒数と、`next_cursor` を `cursor` に指定すると続きから辿れることを含む。終えられたときは `null` |
| `unmatched_scan.next_cursor` | 文字列 / `null` | 辿る時間の上限で止まったときの続きの位置。最後まで辿れたときは `null` |
| `indexes[].index` | 文字列 | チェックした索引の場所。フックが読む順 |
| `indexes[].origin` | `global` / `project` | 索引の出所。`global` は `global.indexes`（無ければユーザーの既定の索引）、`project` はヒットした `projects[].indexes` とプロジェクトの既定の配置場所の索引 |
| `indexes[].hook_error` | 文字列 / `null` | フックがその索引を読めない理由。書式の誤りは行の番号を含む。読めたときは `null` |
| `indexes[].violations[]` | オブジェクトのリスト | JSON Schema への違反の `location` と `reason` |
| `indexes[].missing_rules[]` | オブジェクトのリスト | ルールの場所にファイルが無いエントリの `position` と、解いた `rule` |
| `indexes[].skipped_entries[]` | オブジェクトのリスト | フックが読み飛ばすエントリの `position` と `reason` |
| `indexes[].unmatched_paths[]` | オブジェクトのリスト | `paths` がプロジェクトのどのファイルにもヒットしないエントリの `position`・`rev`・解いた `rule`。`origin` が `global` の索引は `include_global` が `true` のときだけ記載する |
| `indexes[].unused_tag_patterns[]` | オブジェクトのリスト | 使用中のどのタグにもヒットしないタグのパターンの `position`・`rev`・`location`（`args` か `read_by[1].args`）・`key`（`filter[tags]`）・`pattern`（索引に記載したまま）。`global` と `project` のどちらの索引も記載する |
| `tag_check.state` | `checked` / `skipped` / `no_patterns` | タグのパターンの確認の結果。`checked` は dev-docs のタグに照らした、`skipped` は dev-docs に届かない、または読める文書が 0 件で飛ばした、`no_patterns` は確認するパターンが無く dev-docs に問い合わせなかった。`checked` 以外のときはどの索引の `unused_tag_patterns` も空 |
| `tag_check.reason` | 文字列 / `null` | 飛ばした理由。`skipped` のとき、接続先と、接続できない・待ち時間の上限を超えた・エラーを返却した・読める文書が 0 件だったのどれかを含む。それ以外は `null` |

<!-- /table -->

`violations[].location` は、キーを `.`、リストの要素を `[位置]` で結ぶ（例 `rules[0].read_by[1].tools`）。最上位の違反は `$`。

- `unmatched_paths` で確認するのは、有効なエントリ（`enabled: false`・読み飛ばすエントリ・フックが読めない索引のエントリを除く）のうち `paths` を持つもの。`tools` だけのエントリは確認しない
- ヒットするかは、フックと同じ照合（`paths` と `exclude`。`on` は問わない）を、`project_dir` の下のファイルの絶対パスに適用して決める
- 既定では、`origin` が `project` の索引だけを確認する。`include_global` を `true` にすると、`origin` が `global` の索引の分も、`project` の索引の分とは分けて返却する
- `project_dir` の下を `.git` だけ除いて辿る。`.gitignore` で除いたファイルも辿り、フォルダへのシンボリックリンクは辿らない。辿る順はパスの部品ごとの名前の順
- 1 回の呼び出しで辿る時間は 30 秒まで。超えたら辿るのをやめ、`unmatched_scan.completed` を `false` にして、どの索引の `unmatched_paths` も返却せず、`unmatched_scan.next_cursor` を返却する
- `next_cursor` を `cursor` に指定して再度呼び出すと、続きから辿る。`project_dir`・`include_global` は前の呼び出しと同じ値で指定する。確認するエントリが前の呼び出しの後に変わっていたときは、`cursor` を使用せず最初のファイルから再度辿る
- `hook_error`・`violations`・`missing_rules`・`skipped_entries` の確認は、`cursor` によらず毎回全て行う
- `unused_tag_patterns` で確認するのは、有効なエントリ（`unmatched_paths` と同じ除外）の `args` と `read_by[].args` のうち、キーが `[tags]` で終わる条件のパターン。ドットの道筋のキー（`filter.tags`）は確認しない
- パターンは、フックと同じ照合（glob・正規表現）で、dev-docs が返却したタグそのものか、NFKC と `casefold` で正規化したタグのどちらかにヒットすれば使用中とする
- 確認するパターンが 1 つ以上あるときだけ、1 回の呼び出しにつき 1 回、設定ファイルの `global.dev_docs_url` の dev-docs の `search_docs` を `source: "*"`・`group_by: "tags"`・`cwd: project_dir` で呼び、使用中のタグを取得する。索引ごとには問い合わせ修正しない
- dev-docs への問い合わせは、`paths` のヒットしないエントリを確認するファイルの走査と並べて行う。応答を待つ時間は問い合わせを始めてから 207 秒までで、1 回の呼び出しは長くて 212 秒かかる
- dev-docs に接続できない・待ち時間の上限を超えた・`isError` が `true` のとき、`project_dir` から読める文書が 0 件のときは、ツールのエラーにせず `tag_check.state` を `skipped` にして理由を返却する。ほかの確認は変わらない
- `write_index_entry`・`delete_index_entry` の書き込み前のチェックには、`unmatched_paths`・`unused_tag_patterns` を含めない

`cursor` が読めないとき、または `project_dir`・`include_global` が `cursor` を返却した呼び出しと違うときは、`isError: true` になり、`cursor` を省いて再度呼び出す旨を返却する。

## write_index_entry

設定ファイルで読む索引に、エントリを末尾へ新規作成するか、位置で指したエントリのキーを書き換える。
記載した後の索引に新しい問題が出るときは書き込まない。

<!-- table: data -->

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `index` | 文字列 | ✅ | - | 書き込む索引の場所。絶対パスか `~` で始まるパス。設定ファイルで読む索引に限る |
| `entry` | オブジェクト | ✅ | - | 書き込むキーと値。キーは `rule`・`paths`・`exclude`・`tools`・`args`・`on`・`read_by`・`read_tool`・`enabled`。`position` が無いときは新しいエントリの全てのキー、あるときは書き換えるキーだけを指定する（指定しないキーはそのまま残る） |
| `position` | 整数 | - | `rules` の末尾に新規作成する | 書き換えるエントリの位置。0 以上 |
| `expected_rev` | 文字列 | - | なし | 書き換える前のエントリのバージョン。`position` を指定するときは必須 |
| `remove_keys` | 文字列のリスト | - | キーを削除しない | エントリから削除するキー。`position` を指定するときだけ使用し、`entry` と同じキーは指定できない |
| `dry_run` | 真偽値 | - | `false` | 書き込まずにチェックと差分だけを返却するか |

<!-- /table -->

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 常に `true`。書き込めないときは `isError: true` |
| `output` | 文字列 | 書き込んだ索引と位置の 1 行 |
| `index` | 文字列 | 書き込んだ索引の場所（`~` を展開した後） |
| `position` | 整数 | 書き込んだエントリの位置 |
| `rev` | 文字列 | 書き込んだ後のエントリのバージョン |
| `written` | 真偽値 | 索引のファイルを書き換えたか。`dry_run` のときは `false` |
| `diff` | 文字列 | 書き換えの前後の unified diff。前後 3 行を添える |

<!-- /table -->

- 書き込める索引は、`project_dir` で設定ファイルから決まる読む索引だけ。シンボリックリンクを解いた場所で比べる
- 書き込みは、索引を読む → バージョンを比べる → 変更を適用する前と後をチェックする → 同じフォルダの一時ファイルに記載して置き換える、の順。書き込まなかったときは索引のファイルを変えない
- チェックは `check_indexes` と同じ内容で、記載した後にフックが読めないか、記載する前に無かった問題が出るときだけ断る。もとからある問題では断らない
- 対象のエントリの外の行（コメント・引用符・字下げ・キーの並び・改行）は変えない。字下げと改行は索引に合わせる
- 新しく記載する文字列のリストは 1 行のフロー形式、`args` はブロックのマップ、`read_by` はブロックのリスト、`read_tool` はブロックのマップ（`tool`・`args`・`optional_args` の順。`args`・`optional_args` は単一引用符の文字列）で記載する
- 同じ索引への書き込みは、サーバーの中で 1 つずつ行う
- 記載した内容は、再起動せずに次のツールの呼び出しとフックの呼び出しから有効になる

次のときは `isError: true` になる。

<!-- table: data -->

| 条件 | 返却する内容 |
| --- | --- |
| `position` を指定して `expected_rev` を指定しない・`position` が無いのに `remove_keys` を指定する・`entry` と `remove_keys` に同じキーがある | 指定方法 |
| `index` が設定ファイルで読む索引でない | その旨と、読む索引の場所 |
| 索引のファイルが無い・読めない・YAML として読めない・最上位がマップでない | 索引の場所と理由 |
| `position` が索引のエントリの数以上 | 位置が無い旨とエントリの数 |
| `position` を指定し、索引が YAML としては読めるがフックが読めない | フックが読めない理由（行の番号を含む）と、索引を手で修正する旨。`position` を指定しない新規作成も、記載した後にフックが読めないため断る |
| `expected_rev` が今のエントリのバージョンと違う | 今のバージョンと、`list_rules` を再取得してから再度呼び出す旨 |
| 記載した後にフックが読めない・記載する前に無かった問題が出る | 新しく出た問題ごとの `{索引の中の場所}: {理由}` の行 |
| 書き出すと対象のエントリの外の行が変わる（他のエントリが `~`・アンカーなどを持つ） | 索引の書式を保って記載できない旨、最初に変わる行の番号、索引を手で修正する旨 |

<!-- /table -->

## delete_index_entry

設定ファイルで読む索引から、位置で指したエントリを削除する。
Claude Code の許可の設定で削除だけを止められるように、書き込みと別のツールにしている。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `index` | 文字列 | ✅ | - | エントリを削除する索引の場所。`write_index_entry` の `index` と同じ |
| `position` | 整数 | ✅ | - | 削除するエントリの位置。0 以上 |
| `expected_rev` | 文字列 | ✅ | - | 削除するエントリのバージョン |
| `dry_run` | 真偽値 | - | `false` | 書き込まずに差分だけを返却するか |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 常に `true`。削除できないときは `isError: true` |
| `output` | 文字列 | 削除した索引と位置の 1 行 |
| `index` | 文字列 | 削除した索引の場所（`~` を展開した後） |
| `rule` | 文字列 | 削除したエントリの `rule`（索引に記載したまま） |
| `written` | 真偽値 | 索引のファイルを書き換えたか。`dry_run` のときは `false` |
| `diff` | 文字列 | 書き換えの前後の unified diff |

<!-- /table -->

- 削除した位置より後ろのエントリは、位置が 1 つずつ前へずれる。続けて書き込むときは `list_rules` を再取得する
- 対象のエントリの行と、そのエントリに付いたコメントだけを除く。次のエントリの直前に配置したコメントは、次のエントリに付くものとして残す
- チェックは行わない。もとからある問題で削除を止めない

`isError: true` になる条件は `write_index_entry` と同じ（`project_dir` が絶対パスでない・設定ファイルが読めない・読む索引でない・索引が読めない・フックが読めない・位置が無い・バージョンが合わない）。
フックが読めない索引（`rules` をフロー形式で記載した索引を含む）からは削除できないため、手で修正する。

## get_read_records

セッションの既読のルールごとに、今の本文が既読にした時点と同じかと、既読の履歴（`{session_id}.history.jsonl`）に残る読み方を返却する。
`session_id` を省くと、既読の記録のあるセッションの一覧を返却する。
既読の記録と既読の履歴は読むだけで、書き換えない。

記録フォルダは、フックと同じ設定（`global.state_dir`、既定 `${XDG_STATE_HOME:-~/.local/state}/rule-inject`）から決め、`project_dir` は受けない。
サーバーは Claude Code のセッションの ID を受け取らないため、`session_id` で指す。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `session_id` | 文字列 | - | セッションの一覧を返却する | 確認するセッションの識別子。フックが記録ファイル名に使用できる形式 |
| `limit` | 整数 | - | `100` | 返却するルール（`session_id` を省いたときはセッション）の件数の上限。1〜500 |
| `cursor` | 文字列 | - | 先頭から返却する | 前の応答の `next_cursor` |
| `format` | `markdown` / `json` | - | `markdown` | 応答の形式。`list_rules` と同じ |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 確認できたか。記録の無いセッションでも `true` |
| `output` | 文字列 | ルールまたはセッションの件数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所 |
| `state_dir` | 文字列 | 読んだ記録フォルダ |
| `session_id` | 文字列 / `null` | 確認したセッション。`session_id` を省いたときは `null` |
| `rules[].location` | 文字列 | 既読のルールの場所。既読の記録に初めて現れた順。`session_id` を省いたときは空 |
| `rules[].state` | `current` / `changed` / `missing` | 今の本文と既読にした時点の本文の関係 |
| `rules[].reads[]` | オブジェクトのリスト | 既読の履歴に残る読み方。`method`（`read` / `bash` / `mcp`）・`tool`（既読にしたツールの名前）・`last_time`（最後に既読にした時刻）・`count`（既読にした回数）。履歴にその場所の行が無ければ空 |
| `sessions[]` | オブジェクトのリスト | 既読の記録のあるセッション。`session_id`・`updated_at`（既読の記録のファイルの最終更新の時刻）・`rule_count`（既読のルールの場所の数）。最終更新の新しい順。`session_id` を指したときは空 |
| `total` | 整数 | ルールまたはセッションの総数 |
| `next_cursor` | 文字列 / `null` | 続きを取るときに `cursor` へ指定する値。続きが無いときは `null` |

<!-- /table -->

- `state` の `current` は、その場所の既読の記録のどれかの行のハッシュが今の本文のハッシュと同じ（案内では既読）。`changed` はどの行とも違う（案内では未読）。`missing` はその場所にファイルが無い
- `reads` は、読み方とツール名の組ごとに 1 行にまとめる。JSON として読めない行・キーの欠けた行は読み飛ばし、既読の記録に無い場所の行は返却しない
- 応答が長さの上限を超えるときは、その手前のルールまたはセッションで切って `next_cursor` を返却する

次のときは `isError: true` になる。

- `session_id` が記録ファイル名に使用できない形式（受けた値と、形式が誤っている旨を返却する）
- 呼び出しの時点で設定ファイルが読めない（場所と理由を返却する）

## delete_read_records

セッションの既読の記録（`{session_id}.txt`）と案内済みの記録（`{session_id}.guided.txt`）をファイルごと削除し、既読だったルールの場所を返却する。
削除したルールは、フックの次の呼び出しから、止める案内と止めない案内を初めから出す。

記録フォルダは `get_read_records` と同じで、`project_dir` は受けない。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `session_id` | 文字列 | ✅ | - | 既読の記録を削除するセッションの識別子。`get_read_records` の `session_id` と同じ |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 削除を終えたか。記録の無いセッションでも `true` |
| `output` | 文字列 | 削除した既読のルールの件数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所 |
| `state_dir` | 文字列 | 削除した記録フォルダ |
| `session_id` | 文字列 | 削除したセッション |
| `locations` | 文字列のリスト | 削除する前に既読だったルールの場所。既読の記録に初めて現れた順。記録が無かったときは空 |

<!-- /table -->

- 削除は、圧縮の前にフックが行う削除と同じ。既読の履歴（`{session_id}.history.jsonl`）とほかのセッションの記録は削除しない
- 削除の単位はセッションで、ルールの場所ごとの削除はしない
- 記録の無いセッションはエラーにせず、空の `locations` を返却する
- フックが追記している途中でも削除する。削除の後に追記された行は残る

次のときは `isError: true` になり、何も削除しない。

- `session_id` が記録ファイル名に使用できない形式（受けた値と、形式が誤っている旨を返却する）
- 呼び出しの時点で設定ファイルが読めない（場所と理由を返却する）

## get_server_status

サーバー自身の待ち受けのポート・プロセス・起動した時刻・バージョン・クローンの commit と、設定ファイルを読めるかを返却する。
引数は無い。
再起動の途中でも受け付ける。

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 状態を取れたか。設定ファイルが読めなくても `true` |
| `output` | 文字列 | バージョン・commit・ポートの 1 行 |
| `port` | 整数 | 待ち受けているポート。起動時に読んだ `RULE_INJECT_PORT`（無ければ既定のポート） |
| `pid` | 整数 | サーバーのプロセス ID。再起動の後も変わらない |
| `started_at` | 文字列 | 待ち受けを始めた時刻（UTC の ISO 8601）。再起動のたびに新しくなる |
| `version` | 文字列 / `null` | クローンの `version.ini` の値 |
| `clone` | 文字列 | サーバーが動いているクローンの直下 |
| `commit` | 文字列 / `null` | クローンの `HEAD` の commit。git のリポジトリでないときは `null` |
| `config.path` | 文字列 / `null` | 読んだ設定ファイルの場所。既定のパスにファイルが無く読まなかったときは `null` |
| `config.readable` | 真偽値 | 設定ファイルを読めたか |
| `config.error` | 文字列 / `null` | 読めなかった理由（場所と理由） |
| `restarting` | 真偽値 | 再起動を始めた後で、まだ待ち受けを閉じていないか |

<!-- /table -->

## reload_settings

設定ファイルを再読込し、読めたかと、読んだ値を返却する。
設定ファイルはどのツールも呼び出しのたびに再読込しているため、修正した値は次の呼び出しから有効になる。
待ち受けのポートは起動したプロセスの環境変数だけから読むため返却しない（変えたときは、サーバーを起動する環境の `RULE_INJECT_PORT` を変えて再起動する）。

| 引数 | 型 | 必須 | 既定値 | 内容 |
| --- | --- | --- | --- | --- |
| `project_dir` | 文字列 | - | 省くと `global.indexes`（無ければユーザーの既定の索引）だけを返却する | 読む索引を決めるプロジェクトの直下。絶対パス |

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 読めたか |
| `output` | 文字列 | 設定ファイルの場所と読む索引の数の 1 行 |
| `config_path` | 文字列 / `null` | 読んだ設定ファイルの場所 |
| `indexes` | 文字列のリスト | 読む索引の場所。フックが読む順 |
| `state_dir` | 文字列 | 既読の記録とログを配置する記録フォルダ |
| `record_retention_days` | 整数 | 既読の記録の保持期間（日） |
| `log_retention_days` | 整数 | ログの保持日数 |
| `dev_docs_url` | 文字列 | `check_indexes` が問い合わせる dev-docs の接続先 |

<!-- /table -->

設定ファイルが読めないときは `isError: true` になり、場所と理由を返却する。
待ち受けは止めない。

## restart_server

応答を返却した後、処理中のツールの呼び出しの終わりを待ってから待ち受けを閉じ、同じプロセスのまま再起動する。
引数は無い。
再起動の結果は、再接続してから `get_server_status` の `started_at` で確認する。

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 再起動を始めたか |
| `output` | 文字列 | 再起動を始めた旨の 1 行 |
| `pid` | 整数 | 再起動した後も変わらないプロセス ID |
| `restarting` | 真偽値 | 常に `true` |

- 処理中の呼び出しを待つのは最大 356 秒。待つ間も待ち受けを続け、`get_server_status` 以外のツールの呼び出しは断る
- 待ち受けを閉じた後に残った接続は 3 秒で切る。Claude Code の接続は切れるので、`/mcp` で再接続する
- 環境変数は起動時の値を引き継ぐ。`RULE_INJECT_PORT`・`RULE_INJECT_CONFIG` を変えても、この再起動では変わらない
- 再起動の途中か、`update_server` が動いている間は `isError: true` になる

## update_server

サーバーのクローンで上流の commit を fast-forward で取り込み、依存を再インストールし、設定の移し替えが要らなければ再起動する。
引数は無い。

<!-- table: data -->

| 応答のキー | 型 | 内容 |
| --- | --- | --- |
| `success` | 真偽値 | 更新を終えたか |
| `output` | 文字列 | 結果の 1 行。`migration_required` のときは `global-setup` の実行の案内を含む |
| `state` | `up_to_date` / `restarting` / `migration_required` | 何も変えなかった・取り込んで再起動を始めた・取り込んだが移し替えが要るため再起動しなかった |
| `before` | 文字列 | 更新の前の `HEAD` |
| `after` | 文字列 | 更新の後の `HEAD` |
| `steps` | 文字列のリスト | 適用する移し替えの手順。`migration_required` 以外は空 |

<!-- /table -->

- 順に、commit していない変更の確認・`git fetch`・前後の確認・`git merge --ff-only`・`uv sync --extra server`・`python -m rule_inject.migrate --plan` を実行する
- クローンが上流と同じか、上流より先に進んでいるだけのときは `up_to_date` で、何も変えない
- 設定ファイルの `version` だけが古いときは移し替えが要らないものとして再起動する。設定ファイルは書き換えない
- `migration_required` のときは、`/rule-inject:global-setup` で手順を確認してから適用し、続けて `restart_server` を呼ぶ
- コマンドの上限は、git の各コマンド 49 秒・`uv sync` 864 秒・`migrate --plan` 57 秒

次のときは `isError: true` になり、再起動しない。

- 追跡しているファイルに commit していない変更がある（変更のあるファイルを返却し、取得もしない）
- クローンと上流が分かれていて fast-forward できない（両方の commit を返却し、クローンに触らない）
- クローンのブランチに上流が設定されていない
- コマンドが失敗したか上限を超えた（コマンド・終了コード・標準エラーの末尾と、その時点の `HEAD` を返却する）
- 再起動の途中か、別の `update_server` が動いている
