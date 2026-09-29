"""MCP サーバーの起動。`python -m rule_inject.server` で stdio のサーバーを動かす。"""

from __future__ import annotations

import os

from rule_inject.server.app import build_server


def main() -> None:
    """環境変数を渡して組み立てたサーバーを stdio で動かす。"""
    build_server(os.environ).run()


if __name__ == "__main__":
    main()
