# MCP サーバー

## 現状

| 分類 | ページ / ファイル | 概要 | 補足 |
| --- | --- | --- | --- |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/サーバーの起動.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC%E3%81%AE%E8%B5%B7%E5%8B%95.py.yaml) | サーバーの起動 | ツールの一覧の期待値に管理のツールを追加する。待ち受けを `timeout_graceful_shutdown` を渡した `uvicorn.Server` に替える。再起動の後も同じ待ち受けの順番を通す |
| ドキュメント | [設計書/インターフェース定義/MCPサーバー/index.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/MCP%E3%82%B5%E3%83%BC%E3%83%90%E3%83%BC/index.yaml) | MCP サーバーのインターフェースの目次 | 管理のツールの行を追加する |
| ドキュメント | [設計書/モジュール構成/server/app.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/app.py.yaml) | コンポジションルートとツールの登録 | 管理のツールの登録を追加する |
| ドキュメント | [設計書/モジュール構成/server/__main__.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/__main__.py.yaml) | 起動の入口 | `uvicorn.Server` で待ち受け、再起動で `serve` が返った後に起動し直す処理を追加する |
| ドキュメント | [設計書/モジュール構成/server/types.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB%E6%A7%8B%E6%88%90/server/types.py.yaml) | 応答のモデル | 管理のツールの応答のモデルを追加する |
| ドキュメント | [設計書/インターフェース定義/プラグイン/設定の移し替え.py.yaml](https://github.com/shuhei1101/rule-inject/blob/develop/dev/%E8%A8%AD%E8%A8%88%E6%9B%B8/%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%83%BC%E3%82%B9%E5%AE%9A%E7%BE%A9/%E3%83%97%E3%83%A9%E3%82%B0%E3%82%A4%E3%83%B3/%E8%A8%AD%E5%AE%9A%E3%81%AE%E7%A7%BB%E3%81%97%E6%9B%BF%E3%81%88.py.yaml) | 設定の移し替え（`migrate --plan`） | 出力に `version` の更新を除いた手順 `migrations` を追加する |
| 実装 | [src/rule_inject/server/app.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/app.py) | 7 つのツールの登録 | - |
| 実装 | [src/rule_inject/server/__main__.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/server/__main__.py) | 設定とポートを確かめて待ち受ける | - |
| 実装 | [src/rule_inject/migrate/__main__.py](https://github.com/shuhei1101/rule-inject/blob/develop/src/rule_inject/migrate/__main__.py) | 移し替えの入口 | 出力に `migrations` を追加する |
| 実装 | [tests/integration/server/test_server_start.py](https://github.com/shuhei1101/rule-inject/blob/develop/tests/integration/server/test_server_start.py) | 「サーバーの起動」の結合テスト | ツールの一覧の期待値を修正する |

## 変更方針

| 対象 | 方針 | 補足 |
| --- | --- | --- |
| 状態の確認 | 待ち受けのポート・プロセス ID・起動した時刻・ツールのバージョン（`version.ini`）・クローンの場所と commit・設定ファイルの場所と読めるかを返す | `readOnlyHint` |
| 設定の再読込 | 設定ファイルを読み直し、読めたかと、読んだ値（読む索引・記録フォルダ・保持日数・dev-docs の接続先）を返す。待ち受けのポートは起動したプロセスの環境変数だけから読むため、比べない | - |
| 再起動 | 応答を返し、処理中の呼び出しの終わりを待つ間も待ち受けを続けてから待ち受けを閉じ、`os.execv` で同じプロセスを置き換えて起動し直す。待つ間の再起動・更新の呼び出しは断る | 待つ間は `get_server_status` 以外のツールの呼び出しも断る |
| 更新 | サーバーのクローンで `git fetch`・`git merge --ff-only` と `uv sync --extra server` を実行し、設定の移し替え（`rule_inject.migrate --plan` の `migrations`）が要らなければ再起動する。要るときは再起動せず、手順と `global-setup` を返す | 上流に新しい commit が無いときは何も変えずに返す。commit していない変更があるときはクローンに触らない |
| 打ち切りの時間 | 停止の待ち 356 秒、待ち受けを閉じた後の接続の待ち 3 秒、git の各コマンド 49 秒・`uv sync` 864 秒・`migrate --plan` 57 秒（非機能要件「再起動の停止の待ち」「待ち受けを閉じた後の接続の待ち」「更新のコマンドの打ち切り」） | 規約『資源の値の決め方』で導いた |
| ツールの置き場所 | 管理のツールを今のツールと同じ `/mcp` に登録し、実装を `server/admin_tools.py` に置く | - |

## 設計書の確定コミット

| 工程 | 範囲 | 補足 |
| --- | --- | --- |
| 単一ユースケース設計 | `5a022ad..3055832` | - |
| 単一ユースケース設計 | `5009e46..81a086a` | レビューの指摘の修正 |
| インターフェース定義設計 | `904f898..8781254` | 単一ユースケースの任意の指摘（更新の流れの待ち）も含む |
| インターフェース定義設計 | `1720c6d..c66bbee` | レビューの指摘の修正 |

## テスト結果

### 単体

なし

### 結合

なし
