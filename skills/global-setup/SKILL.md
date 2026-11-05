---
name: global-setup
description: 端末ごとに 1 回、rule-inject の端末の設定・MCP サーバーの起動・フックの確認を用意する。入れ直し・端末の移行・更新のあとにも使う
argument-hint: "[--clone パス] [--config パス] [--index パス] [--service 名前] [--yes|--no]"
---

# global-setup

`$ARGUMENTS` の引数で指定しなかった値は、`AskUserQuestion` で既定値を推奨の選択肢にして質問する。
`--yes` は確認に了承、`--no` は確認に断りとして回答する。
質問できないときに値が足りなければ、足りない引数を示して止まる。

## 手順

済んでいる手順は飛ばして、続きから進む。

1. 依存を確認する。
   - `--clone` のクローンで `uv sync --extra server` を実行する
   - `uv` が無いか失敗したら、導入の方法を示して止まる。何も記載しない

2. 端末の設定のパスを決める。
   - `--config`、`RULE_INJECT_CONFIG`、`${XDG_CONFIG_HOME:-~/.config}/rule-inject/settings.yaml` の順に使用する

3. 設定を移し替える。ファイルがある場合だけ実行する。
   - クローンで `RULE_INJECT_CONFIG={パス} uv run --extra server python -m rule_inject.migrate --plan` を実行する
   - 終了コード 6 は、両方のバージョンとプラグインの更新を案内して止まる。何も記載しない
   - 終了コード 1 は、場所と理由を示して止まる。何も記載しない
   - 標準出力の `steps` が空なら手順 5 へ進む
   - `steps` を示して確認する。断られたら、適用しなかった手順を示して止まる。何も記載しない
   - `--plan` を除いて実行し、適用した手順と `backup` のパスを示す。`env` の値は手順 6 で使用する

4. ファイルが無い場合、端末の設定を作る。
   - クローンの `settings.sample.yaml` を元に、`version` をツールのバージョン、`global.indexes` を `--index` の値にして作る
   - 例の値のキーは削除する

5. 旧い登録を確認する。
   - `claude mcp get rule-inject` でユーザースコープの登録があれば、削除してよいかを確認する
   - 了承されたら `claude mcp remove -s user rule-inject` を実行する。断られたら登録を残して続ける

6. `env` を記載する。
   - 記載先は `${CLAUDE_CONFIG_DIR:-~/.claude}/settings.json` の `env`
   - 設定のパスが既定と違うときの `RULE_INJECT_CONFIG` と、手順 3 の `env` の値だけを記載する
   - `env` のほかのキーと、ファイルのほかの内容は変えない

7. サーバーを起動する。
   - ポートは手順 3 の `RULE_INJECT_PORT`、スキルの環境の `RULE_INJECT_PORT`、`8783` の順に使用する
   - `http://127.0.0.1:{ポート}/mcp` に `tools/list` を要求して応答があれば、手順 8 へ進む
   - 応答が無ければ `~/.config/systemd/user/{サービス名}.service` を配置する（サービス名の既定は `rule-inject`）
     - `WorkingDirectory` はクローン、`ExecStart` は `uv run --extra server python -m rule_inject.server`、`SuccessExitStatus=143`
     - `Environment=` に、既定と違うポートの `RULE_INJECT_PORT` と、既定と違うパスの `RULE_INJECT_CONFIG` を記載する
   - `systemctl --user daemon-reload` と `systemctl --user enable --now {サービス名}` を実行する
   - もう一度 `tools/list` を要求する。`list_rules` を含む一覧が返らなければ、記載したものを残し、済んだ手順と止まった手順・`journalctl --user -u {サービス名}`・修正方法を示して止まる

8. フックを確認する。
   - `${CLAUDE_PLUGIN_ROOT}/hooks/run.py rule_guide` に試しの `PreToolUse` の入力を指定し、JSON が返ることを確認する
   - 返らなければ、記載したものを残し、ログのフォルダを示して止まる

9. 結果を示す。
   - 作ったもの・`env` に記載したキー・削除した登録・接続の結果を示す
   - このセッションで MCP を使用するには `/mcp` で接続し直すことを案内する。`env` を記載したときは Claude Code を起動し直すことを案内する
   - リポジトリの索引を登録する `/rule-inject:setup` を案内する
