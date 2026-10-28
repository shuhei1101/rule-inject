"""起動の入口（`python -m rule_inject.server`）。"""

import os
import socket
import sys

from rule_inject.server.app import build_server
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.settings import load_settings

# 待ち受けのアドレス（ループバックだけ）
HOST = "127.0.0.1"
# 起動に失敗したときの終了コード
FAILURE_EXIT_CODE = 1


def main() -> None:
    """設定ファイルとポートを確かめ、`HOST` のポートで Streamable HTTP として待ち受ける。"""
    env = os.environ
    # 設定ファイルが読めなければ、待ち受けずに場所と理由を書いて終わる
    try:
        settings = load_settings(env)
    except SettingsReadError as exc:
        print(f"{exc.path}: {exc.reason}", file=sys.stderr)
        sys.exit(FAILURE_EXIT_CODE)
    # uvicorn は待ち受けの失敗を自分のログに書いて終わるため、先に待ち受けられるかを確かめる
    try:
        socket.create_server((HOST, settings.server_port)).close()
    except OSError as exc:
        print(
            f"{HOST}:{settings.server_port} で待ち受けられない（別のプロセスが使っている）: {exc}",
            file=sys.stderr,
        )
        sys.exit(FAILURE_EXIT_CODE)
    # Ctrl+C・SIGTERM は uvicorn が待ち受けを閉じてから終わる
    build_server(env).run("streamable-http", host=HOST, port=settings.server_port)


if __name__ == "__main__":
    main()
