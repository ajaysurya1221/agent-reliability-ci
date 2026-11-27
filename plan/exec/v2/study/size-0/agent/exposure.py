"""Record the actual first HTTP request and its synchronous NDJSON stream."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import httpx
from pydantic import JsonValue
from wire import observe


class ReceiptLost(Exception):
    """The wire completed but the receipt still describes an incomplete exchange."""


class FirstExchange:
    def __init__(self, path: str, task: dict[str, JsonValue], seed: int, arm: str) -> None:
        run = os.environ["SIZE0_RUN"]
        (assignment,) = (
            a
            for a in json.loads(Path(os.environ["SIZE0_ASSIGNMENTS"]).read_bytes())
            if (a["run"], a["seed"], a["order_id"], a["arm"]) == (run, seed, task["order_id"], arm)
        )
        self.row = {k: assignment[k] for k in ("run", "round", "order_id", "arm", "seed")}
        self.path = Path(path) / f"{assignment['round']}-{arm}-{seed}.json"
        self.row.update(
            body_sha256=None,
            host=None,
            port=None,
            method=None,
            path=None,
            response_model=None,
            stream_completed=False,
            incomplete_reason="no_response_headers",
            model_mismatch=False,
        )
        self.owns_receipt = False
        self.first: httpx.Request | None = None

    def on_request(self, request: httpx.Request) -> None:
        if self.first is None:
            self.first = request
            self.row.update(
                body_sha256=hashlib.sha256(request.content).hexdigest(),
                host=request.url.host,
                port=request.url.port,
                method=request.method,
                path=request.url.raw_path.decode(),
            )

            # A worker killed in the client must still leave the observed outbound request.
            self.publish(create=True)
            self.owns_receipt = True

    def on_response(self, response: httpx.Response) -> None:
        if response.request is not self.first:
            return

        self.row["incomplete_reason"] = "incomplete_stream"

        def frame_seen(frame: dict[str, Any]) -> None:
            model = frame.get("model")
            if model is None:
                return
            if model != self.row["response_model"]:
                self.row["incomplete_reason"] = "incomplete_stream"
                self.row["response_model"] = model
                self.row["model_mismatch"] |= model != os.environ["SIZE0_TAG"]
                self.record()

        try:
            reason = observe(response, frame_seen)
        except httpx.TransportError:
            self.row["incomplete_reason"] = "transport_error"
            self.record()
            raise
        self.row.update(stream_completed=reason is None, incomplete_reason=reason)
        try:
            self.record()
        except BaseException as exc:
            if reason is None:
                raise ReceiptLost("SIZE_ZERO_RECEIPT_LOST") from exc
            raise

    def record(self) -> None:
        if self.owns_receipt:
            self.publish(create=False)

    def publish(self, *, create: bool) -> None:
        with NamedTemporaryFile(dir=self.path.parent, delete=False) as stream:
            tmp = Path(stream.name)
            try:
                stream.write(json.dumps(self.row).encode())
                stream.flush()
                os.fsync(stream.fileno())
                if create:
                    # Atomic exclusive publication keeps concurrent writers visible.
                    try:
                        os.link(tmp, self.path)
                    except FileExistsError:
                        self.path.with_suffix(".duplicate").touch()
                        raise
                else:
                    tmp.replace(self.path)
            finally:
                tmp.unlink(missing_ok=True)
