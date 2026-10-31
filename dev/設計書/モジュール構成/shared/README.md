# shared

フックが共有する設定・場所の解決・ログ・例外の物理ファイルごとのモジュール

## 目次

<!-- table: data -->

| ページ | 概要 |
| --- | --- |
| [errors.py](./errors.py.yaml) | 設定ファイル・索引の読み取りと編集・既読の記録・既読の履歴・ログの例外 |
| [paths.py](./paths.py.yaml) | 既定の記録フォルダ・ログのフォルダとルールの場所の解決 |
| [settings.py](./settings.py.yaml) | 設定ファイルの読み取りと projects の当て方 |
| [_settings_yaml.py](./_settings_yaml.py.yaml) | 設定ファイルの YAML の一部だけを読む |
| [variables.py](./variables.py.yaml) | !{名前} を環境変数の値へ展開する |
| [logger.py](./logger.py.yaml) | 失敗を日付ごとのログ（JSON Lines）へ書き、古いログを削除する |

<!-- /table -->
