"""Byte-for-byte relay between an MCP stdio client and a Unix socket."""

from __future__ import annotations

import argparse
import contextlib
import os
import socket
import sys
import threading
from collections.abc import Callable


def _pump(
    read: Callable[[int], bytes], write: Callable[[bytes], object], done: threading.Event
) -> None:
    try:
        while not done.is_set():
            chunk = read(65536)
            if not chunk:
                return
            write(chunk)
    except (BrokenPipeError, ConnectionError, OSError):
        pass
    finally:
        done.set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m arci.mcp_shim")
    parser.add_argument("--socket", required=True)
    args = parser.parse_args(argv)

    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        connection.connect(args.socket)
    except OSError:
        connection.close()
        return 2

    done = threading.Event()

    def write_stdout(data: bytes) -> None:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    stdin_fd = sys.stdin.fileno()

    def read_stdin(size: int) -> bytes:
        return os.read(stdin_fd, size)

    threads = (
        threading.Thread(
            target=_pump,
            args=(read_stdin, connection.sendall, done),
            daemon=True,
        ),
        threading.Thread(
            target=_pump,
            args=(connection.recv, write_stdout, done),
            daemon=True,
        ),
    )
    for thread in threads:
        thread.start()
    done.wait()
    with contextlib.suppress(OSError):
        connection.shutdown(socket.SHUT_RDWR)
    connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
