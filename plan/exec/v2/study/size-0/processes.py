"""Match process IDs to kernel start times, including after exec."""

import ctypes
import errno
import os
import struct
import sys
from pathlib import Path


def start_time(pid: int) -> str | None:
    if pid <= 0:
        raise ValueError("invalid recorded process")
    if sys.platform == "darwin":
        # proc_bsdinfo ends with the timeval at which the process started.
        buf = ctypes.create_string_buffer(136)
        lib = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        size = lib.proc_pidinfo(pid, 3, 0, buf, len(buf))
        if not size and ctypes.get_errno() in (errno.ESRCH, errno.ENOENT):
            return None
        if size != len(buf):
            raise OSError(ctypes.get_errno(), "cannot inspect process start")
        sec, usec = struct.unpack_from("=QQ", buf.raw, 120)
        return f"{sec}.{usec:06d}"
    try:
        # Field 22 follows the parenthesized command, which can include spaces.
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        return None


def group_alive(pid: int, started: str) -> bool:
    current = start_time(pid)
    if current is not None and current != started:
        return False
    # An already registered group can outlive its leader. Its PGID cannot be
    # allocated to a new leader while those descendants still belong to it.
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # EPERM does not establish group exit, including during reparenting.
        return True
    return True
