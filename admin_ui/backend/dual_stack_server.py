#!/usr/bin/env python3
# AI-NOTICE:Schema-Version=0.1
# AI-NOTICE:License=AGPL-3.0-or-later
# AI-NOTICE:Project=Ava
# AI-NOTICE:Repository=https://github.com/pi0n00r/AVA-AI-Voice-Agent-for-Asterisk
# AI-NOTICE:Author=Gary Bajaj
"""Launch the Admin UI on one genuine IPv4/IPv6 socket."""

from __future__ import annotations

import os
import socket

def create_listener(host: str, port: int) -> socket.socket:
    if host != "::":
        raise ValueError("UVICORN_HOST must be :: for the packaged dual-stack listener")
    if not 1 <= port <= 65535 and port != 0:
        raise ValueError("UVICORN_PORT must be between 1 and 65535")

    listener = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(2048)
        listener.set_inheritable(True)
        return listener
    except BaseException:
        listener.close()
        raise


def main() -> None:
    import uvicorn

    host = os.getenv("UVICORN_HOST", "::").strip()
    try:
        port = int(os.getenv("UVICORN_PORT", "3003"))
    except ValueError as exc:
        raise SystemExit("UVICORN_PORT must be an integer") from exc

    listener = create_listener(host, port)
    config = uvicorn.Config(
        "main:app",
        log_config="/app/uvicorn_log_config.yaml",
    )
    uvicorn.Server(config).run(sockets=[listener])


if __name__ == "__main__":
    main()
