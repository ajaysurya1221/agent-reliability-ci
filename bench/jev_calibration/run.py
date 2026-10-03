"""Send the audit's requests and seal every answer in a hash-chained JSONL store.

    TYPESAFE_API_KEY=... .venv/bin/python -m bench.jev_calibration.run --dataset clinc150 \
        --passes 3 --out runs/jev-calibration/2026-10-03

The key is read from the environment and never written. Each record carries the vendor's
request id, the reported model and token usage, the client-measured latency, the full answers,
and a SHA-256 over the previous record's hash and its own content.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from bench.jev_calibration.data import CLINC, DATASETS, Dataset, Item, load
from bench.jev_calibration.questions import (
    BASE_URL,
    MODEL,
    JsonValue,
    Question,
    bundled_questions,
    closed_only_questions,
)

SCHEMA = "arci-bench-jev-calibration/1"
PROTOCOL_BUNDLED = "bundled"
PROTOCOL_CLOSED_ONLY = "closed_only"
RETRY_STATUSES = frozenset({429, 529})
MAX_ATTEMPTS = 6
KEY_ENV = "TYPESAFE_API_KEY"
CHECK_IN_SCOPE = 300
CHECK_OOS = 100


@dataclass(frozen=True)
class Job:
    item: Item
    pass_no: int
    protocol: str


@dataclass(frozen=True)
class Outcome:
    job: Job
    sent_at: str
    status: int | None
    error: str | None
    attempts: int
    latency_ms: float
    request_id: str | None
    body: dict[str, JsonValue] | None


class RateLimiter:
    """A token bucket shared by the worker threads: at most `rate` admissions per second."""

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._tokens = rate
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self._rate, self._tokens + (now - self._updated) * self._rate)
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate
            time.sleep(wait)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def send_once(
    url: str, key: str, body: bytes, timeout: float
) -> tuple[int, str | None, dict[str, JsonValue] | None, str | None, float]:
    """One HTTP attempt: (status, request id, parsed body, retry-after header, latency ms)."""
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "arci-bench-jev-calibration/1",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            latency = (time.perf_counter() - started) * 1000
            parsed = cast(dict[str, JsonValue], json.loads(raw))
            return (
                int(response.status),
                response.headers.get("x-typesafe-request-id"),
                parsed,
                None,
                latency,
            )
    except urllib.error.HTTPError as error:
        latency = (time.perf_counter() - started) * 1000
        detail = error.read()[:300].decode("utf-8", "replace")
        return (
            int(error.code),
            error.headers.get("x-typesafe-request-id"),
            {"error": detail},
            error.headers.get("retry-after"),
            latency,
        )


def perform(
    job: Job, body: bytes, url: str, key: str, limiter: RateLimiter, timeout: float
) -> Outcome:
    sent_at = datetime.now(UTC).isoformat(timespec="milliseconds")
    status: int | None = None
    error: str | None = None
    request_id: str | None = None
    parsed: dict[str, JsonValue] | None = None
    latency = 0.0
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        limiter.acquire()
        retry_after: str | None = None
        try:
            status, request_id, parsed, retry_after, latency = send_once(url, key, body, timeout)
            error = None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            status = None
            parsed = None
            error = f"{type(exc).__name__}: {str(exc)[:200]}"
        if status is not None and status < 400:
            return Outcome(job, sent_at, status, None, attempts, latency, request_id, parsed)
        if status is not None and status not in RETRY_STATUSES:
            detail = canonical(parsed)[:300] if parsed is not None else ""
            return Outcome(
                job,
                sent_at,
                status,
                f"http {status}: {detail}",
                attempts,
                latency,
                request_id,
                None,
            )
        delay = min(30.0, 0.5 * 2**attempts) + random.uniform(0.0, 0.5)
        if retry_after is not None:
            with contextlib.suppress(ValueError):
                delay = max(delay, float(retry_after))
        time.sleep(delay)
    return Outcome(
        job,
        sent_at,
        status,
        error or f"http {status} after {attempts} attempts",
        attempts,
        latency,
        request_id,
        None,
    )


def jobs_for(
    dataset: Dataset, passes: Sequence[int], closed_only: bool, limit: int | None
) -> list[Job]:
    if closed_only:
        in_scope = [item for item in dataset.items if item.label != "oos"][:CHECK_IN_SCOPE]
        out_of_scope = [item for item in dataset.items if item.label == "oos"][:CHECK_OOS]
        return [Job(item, 1, PROTOCOL_CLOSED_ONLY) for item in in_scope + out_of_scope]
    items = dataset.items[:limit] if limit is not None else dataset.items
    return [Job(item, pass_no, PROTOCOL_BUNDLED) for pass_no in passes for item in items]


def done_keys(path: Path) -> tuple[set[tuple[str, int, str]], str, int]:
    """Keys already recorded in `path`, the last record hash and the last sequence number."""
    keys: set[tuple[str, int, str]] = set()
    last_hash = "0" * 64
    last_seq = -1
    if not path.exists():
        return keys, last_hash, last_seq
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = cast(dict[str, JsonValue], json.loads(line))
            keys.add(
                (str(record["item_id"]), int(cast(int, record["pass"])), str(record["protocol"]))
            )
            last_hash = str(record["record_sha256"])
            last_seq = int(cast(int, record["seq"]))
    return keys, last_hash, last_seq


def record_for(outcome: Outcome, seq: int, prev_hash: str, model: str) -> dict[str, JsonValue]:
    body = outcome.body
    record: dict[str, JsonValue] = {
        "schema": SCHEMA,
        "seq": seq,
        "prev_sha256": prev_hash,
        "dataset": outcome.job.item.dataset,
        "item_id": outcome.job.item.item_id,
        "label": outcome.job.item.label,
        "domain": outcome.job.item.domain,
        "pass": outcome.job.pass_no,
        "protocol": outcome.job.protocol,
        "model_requested": model,
        "sent_at": outcome.sent_at,
        "status": outcome.status,
        "error": outcome.error,
        "attempts": outcome.attempts,
        "latency_ms": round(outcome.latency_ms, 1),
        "request_id": outcome.request_id,
        "model": body.get("model") if body is not None else None,
        "usage": body.get("usage") if body is not None else None,
        "answers": body.get("answers") if body is not None else None,
    }
    record["record_sha256"] = sha256_text(prev_hash + "\n" + canonical(record))
    return record


def write_manifest(
    out_dir: Path,
    dataset: Dataset,
    questions: dict[str, Question],
    protocol: str,
    args: argparse.Namespace,
    counts: dict[str, int],
) -> None:
    passes: list[JsonValue] = [int(p) for p in cast(list[int], args.pass_numbers)]
    manifest: dict[str, JsonValue] = {
        "schema": SCHEMA,
        "dataset": dataset.name,
        "items": len(dataset.items),
        "intents": len(dataset.intents),
        "protocol": protocol,
        "model": cast(str, args.model),
        "base_url": cast(str, args.base_url),
        "passes": passes,
        "workers": cast(int, args.workers),
        "requests_per_second": cast(float, args.rps),
        "timeout_seconds": cast(float, args.timeout),
        "questions_sha256": sha256_text(canonical(questions)),
        "questions": cast(JsonValue, questions),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "counts": cast(JsonValue, counts),
    }
    name = f"{dataset.name}.{protocol}.manifest.json"
    (out_dir / name).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--passes", type=int, default=3, help="passes 1..N of identical requests")
    parser.add_argument("--pass-start", type=int, default=1)
    parser.add_argument(
        "--closed-only", action="store_true", help="the bundling independence check"
    )
    parser.add_argument("--limit", type=int, default=None, help="first N items only (debugging)")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--rps", type=float, default=20.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("runs/jev-calibration/data"))
    args = parser.parse_args(argv)
    args.pass_numbers = list(range(int(args.pass_start), int(args.pass_start) + int(args.passes)))

    key = os.environ.get(KEY_ENV, "")
    if not key:
        print(f"{KEY_ENV} is not set", file=sys.stderr)
        return 3
    dataset = load(cast(str, args.dataset), cast(Path, args.cache))
    closed_only = cast(bool, args.closed_only)
    if closed_only and dataset.name != CLINC:
        print("the independence check is defined for clinc150 only", file=sys.stderr)
        return 2
    protocol = PROTOCOL_CLOSED_ONLY if closed_only else PROTOCOL_BUNDLED
    questions = (
        closed_only_questions(dataset.intents)
        if closed_only
        else bundled_questions(dataset.name, dataset.intents)
    )
    out_dir = cast(Path, args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    store = out_dir / f"{dataset.name}.{protocol}.jsonl"
    done, prev_hash, seq = done_keys(store)
    jobs = [
        job
        for job in jobs_for(dataset, args.pass_numbers, closed_only, cast(int | None, args.limit))
        if (job.item.item_id, job.pass_no, job.protocol) not in done
    ]
    print(
        f"{dataset.name}: {len(jobs)} requests to send ({len(done)} already recorded)", flush=True
    )
    url = f"{cast(str, args.base_url).rstrip('/')}/v1/systemone"
    model = cast(str, args.model)
    limiter = RateLimiter(cast(float, args.rps))
    timeout = cast(float, args.timeout)
    counts: dict[str, int] = {"ok": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0}
    latencies: list[float] = []
    started = time.monotonic()
    with (
        store.open("a", encoding="utf-8") as handle,
        ThreadPoolExecutor(cast(int, args.workers)) as pool,
    ):
        futures = []
        for job in jobs:
            body = canonical(
                {"state": job.item.text, "model": model, "questions": questions}
            ).encode("utf-8")
            futures.append(pool.submit(perform, job, body, url, key, limiter, timeout))
        for completed, future in enumerate(as_completed(futures), start=1):
            outcome = future.result()
            seq += 1
            record = record_for(outcome, seq, prev_hash, model)
            prev_hash = str(record["record_sha256"])
            handle.write(canonical(record) + "\n")
            if outcome.body is not None and outcome.error is None:
                counts["ok"] += 1
                usage = cast(dict[str, int], outcome.body.get("usage") or {})
                counts["input_tokens"] += int(usage.get("input_tokens", 0))
                counts["output_tokens"] += int(usage.get("output_tokens", 0))
                latencies.append(outcome.latency_ms)
            else:
                counts["failed"] += 1
            if completed % 500 == 0 or completed == len(futures):
                handle.flush()
                elapsed = time.monotonic() - started
                print(
                    f"  {completed}/{len(futures)} ok={counts['ok']} failed={counts['failed']} "
                    f"{elapsed:.0f}s {completed / elapsed:.1f} req/s",
                    flush=True,
                )
    write_manifest(out_dir, dataset, questions, protocol, args, counts)
    cost = counts["input_tokens"] * 0.042 / 1e6
    ordered = sorted(latencies)
    p50 = ordered[len(ordered) // 2] if ordered else float("nan")
    p95 = ordered[int(len(ordered) * 0.95)] if ordered else float("nan")
    print(
        f"done: ok={counts['ok']} failed={counts['failed']} input_tokens={counts['input_tokens']} "
        f"output_tokens={counts['output_tokens']} est_cost_usd={cost:.3f} "
        f"p50={p50:.0f}ms p95={p95:.0f}ms store={store}",
        flush=True,
    )
    return 0 if counts["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
