"""起動の入口（`python -m rule_inject.server`）。"""

import os
import socket
import sys
from pathlib import Path

import uvicorn

from rule_inject.server.app import build_server
from rule_inject.server.clone import find_clone
from rule_inject.server.control import GRACEFUL_SHUTDOWN_TIMEOUT, ServerControl
from rule_inject.shared.errors import SettingsReadError
from rule_inject.shared.settings import load_settings

# 待ち受けのアドレス（ループバックだけ）
HOST = "127.0.0.1"
# 起動に失敗したときの終了コード
FAILURE_EXIT_CODE = 1


def main() -> None:
    """設定ファイルとポートを確かめ、`HOST` のポートで Streamable HTTP として待ち受ける。再起動で閉じたら同じプロセスで起動し直す。"""
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
    control = ServerControl(port=settings.server_port)
    clone = find_clone(Path(__file__).parent)
    app = build_server(env, control=control, clone=clone).streamable_http_app(host=HOST)
    # MCPServer.run は timeout_graceful_shutdown を渡せず、Server も外へ出さないため、uvicorn.Server で待ち受ける
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=settings.server_port,
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT,
        )
    )
    control.attach(server)
    # Ctrl+C・SIGTERM・再起動は、uvicorn が待ち受けを閉じ、残った接続を上限で切ってから戻る
    server.run()
    # 再起動で戻った: 環境変数を引き継いだまま、同じプロセスを起動の入口で置き換える（戻らない）
    if control.restart_requested:
        os.execv(sys.executable, [sys.executable, "-m", "rule_inject.server"])


if __name__ == "__main__":
    main()
