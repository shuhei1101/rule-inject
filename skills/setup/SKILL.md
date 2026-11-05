---
name: setup
description: リポジトリの索引が rule-inject に読まれる状態にして、索引のチェックの結果を示す
argument-hint: "[索引のパス]"
---

# setup

`$ARGUMENTS` はリポジトリの直下からの索引のパス。省くと直下の `rules.yaml`。

## 手順

1. 端末の設定を確認する。
   - `RULE_INJECT_CONFIG`、`${XDG_CONFIG_HOME:-~/.config}/rule-inject/settings.yaml` の順にパスを決める
   - ファイルが無ければ `/rule-inject:global-setup` を案内して止まる。何も記載しない

2. 索引を確認する。
   - 索引のファイルが無ければ、公開ドキュメント『索引の書式』を案内して止まる。何も記載しない

3. 別の場所の索引を登録する。`$ARGUMENTS` があるときだけ実行する。
   - 端末の設定の `projects` に、`match` がリポジトリの絶対パスの要素を探す
   - 要素があれば `indexes` へ追加し、無ければ `match` と `indexes` を持つ要素を追加する

4. 索引をチェックする。
   - MCP サーバーの `check_indexes` を、`project_dir` をリポジトリの絶対パスにして呼ぶ
   - 呼べなければ、`/rule-inject:global-setup` かサーバーの起動を案内して止まる

5. 結果を示す。
   - 参照する索引のパス・記載した要素・チェックの結果を示す
