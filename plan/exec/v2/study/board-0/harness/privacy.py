import base64
import binascii
import json
import os
import re
import subprocess
from typing import Any
from urllib.parse import unquote

from common import ROOT, need


def operator_identifiers() -> set[str]:
    keys = (
        "HOME",
        "USER",
        "LOGNAME",
        "GIT_USER_NAME",
        "GIT_USER_EMAIL",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    )
    values = {os.environ.get(key, "") for key in keys}
    for name in ("user.name", "user.email"):
        value = subprocess.run(
            ["git", "--no-optional-locks", "config", "--get", name],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=5,
        )
        need(value.returncode in (0, 1), "cannot determine git identity")
        if value.returncode == 0:
            values.add(value.stdout.decode().strip())
    return {v.casefold() for v in values if v}


def safe_bytes(data: bytes, identifiers: set[str] | None = None) -> None:
    private = operator_identifiers() if identifiers is None else identifiers
    path = re.compile(r"/(?:Users/(?!Shared(?:/|\b))|home/)[A-Za-z0-9_.-]+(?:/|\b)")

    class Members(list[tuple[str, Any]]):
        """Retain every JSON member, including duplicate keys in a log."""

    binary_controls = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
    decoder = json.JSONDecoder(object_pairs_hook=Members)
    token = re.compile(r'["{\[]')
    encoded_field = re.compile(
        r"(?:.*_)?(?:b64|base64|data|blob|payload|body|log|logs|content|receipt|ledger|stdout|stderr|request|response)"
    )

    def visit(value: Any, key: str, depth: int) -> None:
        need(depth < 64, "publication payload nesting exceeds scan limit")
        if isinstance(value, Members):
            if any(name in ("blob", "data") for name, _ in value):
                for name, item in value:
                    if name.casefold() in ("mimetype", "content-type") and isinstance(item, str):
                        charset = re.search(r"""(?i)\bcharset\s*=\s*["']?([^;' "]+)""", item)
                        need(
                            charset is None
                            or charset[1].casefold() in {"utf-8", "utf8", "us-ascii"},
                            "uninspectable declared encoding",
                        )
            for name, item in value:
                if key == "resource" and name == "blob":
                    need(isinstance(item, str), "uninspectable resource blob")
                scan(name, "", depth)
                visit(item, name, depth + 1)
        elif isinstance(value, list):
            for element in value:
                visit(element, key, depth + 1)
        elif isinstance(value, str):
            scan(value, key, depth)

    def scan(text: str, key: str = "", depth: int = 0) -> None:
        need(depth < 64, "publication payload nesting exceeds scan limit")
        need("\x00" not in text, "uninspectable text encoding")
        folded = text.casefold()
        need(
            not path.search(text) and not any(v in folded for v in private),
            "personal identifier or path in publication or descriptor",
        )
        if "%" in text and (decoded := unquote(text)) != text:
            scan(decoded, key, depth + 1)
        name = key.casefold()
        strict = name in {"blob", "data", "base64", "b64"} or name.endswith(("_b64", "_base64"))
        if strict or encoded_field.fullmatch(name):
            compact = "".join(text.split())
            if strict or (compact and re.fullmatch(r"[A-Za-z0-9+/_-]+={0,2}", compact)):
                try:
                    decoded_bytes = base64.b64decode(
                        compact if strict else compact + "=" * (-len(compact) % 4),
                        altchars=b"-_",
                        validate=True,
                    )
                    decoded_text = decoded_bytes.decode("utf-8")
                except (binascii.Error, UnicodeDecodeError) as exc:
                    if strict:
                        raise ValueError("uninspectable encoded payload") from exc
                else:
                    if strict:
                        need(
                            not binary_controls.search(decoded_text),
                            "uninspectable encoded payload",
                        )
                    if not binary_controls.search(decoded_text):
                        scan(decoded_text, depth=depth + 1)
        # Find JSON values even in a log with timestamps, prefixes or multiple records.
        offset = 0
        while match := token.search(text, offset):
            try:
                value, offset = decoder.raw_decode(text, match.start())
            except ValueError:
                offset = match.end()
            else:
                visit(value, "", depth + 1)

    scan(data.decode("utf-8", errors="strict"))
