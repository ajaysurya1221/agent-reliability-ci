"""Index, check and reproduce the ci-gate-2026-10-06 evidence package.

Run from any directory with the release environment's interpreter:

    .venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --index
        write evidence-index.json and SHA256SUMS for every package file except this script,
        the index and SHA256SUMS (and Python/OS caches)
    .venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py [--check] [--full] [--strict]
        (a) verify SHA256SUMS and the index's hashes of the evidence outside the package,
        (b) re-derive all 18 archived docs/results/**/decision.json byte for byte, each in a
            clean subprocess on a temporary copy of manifest.json and trials.jsonl,
        (c) regenerate the planner example with `arci plan` and compare it byte for byte
            (an absent `arci plan` is a failure, never a skip),
        (d) with --full, also regenerate metrics/selfcheck-*.json with bench/selfcheck.py
            (minutes) and run docs/results/guardrail/summarize.py --check,
        with --strict, also fail on any `<<...>>` placeholder left in REPORT.md
    .venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --docker
        the two-stage recipe of reproduction/README.md in linux/amd64 (stage 2 with no
        network), logged to logs/docker-reproduce-<date>.txt

Exit codes: 0 every row ok; 1 a mismatch or a failed step; 2 usage error.
Uses only the standard library and the installed `arci`; no network except Docker stage 1.
Archived stores are only read: every regeneration happens in a temporary directory.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PACKAGE = HERE.relative_to(REPO).as_posix()
RESULTS = REPO / "docs" / "results"
INDEX = HERE / "evidence-index.json"
SUMS = HERE / "SHA256SUMS"
REPORT = HERE / "REPORT.md"
METRICS = HERE / "metrics"
LOGS = HERE / "logs"

# Never hashed: this script (a verifier cannot vouch for itself), the two files it writes, and
# interpreter or OS caches.
EXCLUDED_FILES = ("reproduce.py", "evidence-index.json", "SHA256SUMS")
IGNORED_NAMES = frozenset({"__pycache__", ".DS_Store"})

EXPECTED_DECISIONS = 12 + 6  # Jev (five of them invalid attempts) + guardrail
SCRUBBED_ENV = ("TYPESAFE_API_KEY", "jev_key", "GITHUB_STEP_SUMMARY")
GATE_TIMEOUT = 30
PLAN_TIMEOUT = 900  # about 17 s natively; linux/amd64 emulation is much slower
SELFCHECK_TIMEOUT = 3600
SUMMARIZE_TIMEOUT = 300

# The planner example: the acceptance command of PLAN.md, the design in the header of
# metrics/plan-0.95-vs-0.75.md. Both formats are regenerated and compared byte for byte.
PLAN_FLAGS = (
    "--baseline-rate",
    "0.95",
    "--candidate-rate",
    "0.75",
    "--alpha",
    "0.05",
    "--delta",
    "0.10",
    "--n-grid",
    "20,50,100,200,400",
    "--target-verdict",
    "BLOCK",
    "--target-probability",
    "0.80",
)
PLAN_OUTPUTS = (("json", "plan-0.95-vs-0.75.json"), ("markdown", "plan-0.95-vs-0.75.md"))
SELFCHECK_METHODS = ("clopper_pearson", "newcombe")

# REPORT.md placeholders tolerated until the orchestrator fills them (`--strict` tolerates none).
ALLOWED_PLACEHOLDER_FAMILIES = ("REPRO", "WP3", "PLANNER")
PLACEHOLDER = re.compile(r"<<(.*?)>>", re.DOTALL)
PLACEHOLDER_FAMILY = re.compile(r"\s*([A-Z][A-Z0-9_]*)\s*:")

DOCKER_IMAGE = "python:3.11-slim"
DOCKER_PLATFORM = "linux/amd64"
DOCKER_VOLUME = "arci-repro"
PYTEST_PIN = "pytest==9.1.1"  # uv.lock's pytest; the runtime dependencies come from `pip install .`
SEALED_JEV_ROOT = "/home/user/agent-reliability-ci"
SEALED_GUARDRAIL_ROOT = "/Users/ajay/Developer/.arci-worktrees/guardrail-live"
REPLAYS = (
    ("jev", "docs/results/jev/2026-10-03/jev-live-b-low_confidence-200/min-bundle.json"),
    (
        "guardrail",
        "docs/results/guardrail/2026-10-05/guardrail-live-b-ask-provider_down-200/min-bundle.json",
    ),
)
REDERIVATION_TESTS = (
    "tests/unit/stats/test_wilson_quantile_pin.py",
    "tests/unit/examples/test_guardrail_results.py",
)
REPRODUCED_LINE = "REPRODUCED: failure reproduced"
PYTEST_PASS_LINE = re.compile(r"^\s*18 passed\b(?!.*\b(?:failed|error|errors)\b).*$", re.MULTILINE)

# What each known package file is, and what it proves. Anything else gets a generic entry.
DESCRIPTIONS: dict[str, tuple[str, str]] = {
    "PLAN.md": (
        "Plan of record frozen 2026-10-05 21:10 IST: question, starting identities, frozen "
        "decisions, work packages, acceptance commands and permitted claims.",
        "Nothing by itself: it is the specification the package is checked against.",
    ),
    "REPORT.md": (
        "The technical report: gate, planner, worked examples, reproducibility, related work "
        "and limitations.",
        "Nothing by itself: each claim cites a committed source or a file in this index.",
    ),
    "reproduction/README.md": (
        "The two-stage Docker recipe that recreates the bundles' sealed interpreter paths and "
        "replays with networking disabled; documents reproduce.py.",
        "Nothing by itself: the recipe; its outcomes are the docker-* logs.",
    ),
    "metrics/plan-0.95-vs-0.75.json": (
        "`arci plan` output (schema arci.plan.v1): baseline 0.95, candidate 0.75, alpha 0.05, "
        "delta 0.10, N per arm 20,50,100,200,400, target P(BLOCK) >= 0.80, full precision.",
        "The planner's exact verdict probabilities (P(BLOCK) = 0.3647... at N=200; smallest "
        "tested N meeting the target: 400); regenerated byte for byte by `reproduce.py --check`.",
    ),
    "metrics/plan-0.95-vs-0.75.md": (
        "The same plan rendered as Markdown (probabilities rounded to three decimals).",
        "The human-readable planner example; regenerated byte for byte by `reproduce.py --check`.",
    ),
    "metrics/selfcheck-clopper_pearson.json": (
        "`bench/selfcheck.py --method clopper_pearson --json` output: exact operating "
        "characteristics, seeded correlated Monte Carlo, boundary sweep, calibration flags.",
        "The operating-characteristics table of REPORT.md section 3 and the gate's tail "
        "calibration; regenerated with exact value equality by `reproduce.py --check --full`.",
    ),
    "metrics/selfcheck-newcombe.json": (
        "`bench/selfcheck.py --method newcombe --json` output, same structure.",
        "Descriptive Newcombe characteristics only (no exact-coverage claim); regenerated with "
        "exact value equality by `reproduce.py --check --full`.",
    ),
    "logs/selfcheck-clopper_pearson.txt": (
        "Console output of the Clopper-Pearson self-check run that wrote its metrics JSON.",
        "The run completed with every calibration check PASS.",
    ),
    "logs/selfcheck-newcombe.txt": (
        "Console output of the Newcombe self-check run that wrote its metrics JSON.",
        "The run completed; descriptive only.",
    ),
    "logs/docker-replay-probe-2026-10-05.txt": (
        "Preliminary probe of the Docker recipe from main f299854 (linux/amd64, network none).",
        "Both committed minimised bundles printed REPRODUCED and exited 0; preliminary, "
        "superseded by the docker-reproduce log.",
    ),
    "logs/docker-rederive-2026-10-05.txt": (
        "Preliminary run of the byte-exact re-derivation tests in the probe container "
        "(network none).",
        "Preliminary: the 18 committed decisions re-derived on linux/amd64; superseded by the "
        "docker-reproduce log.",
    ),
    "logs/hero-demo-2026-10-05.txt": (
        "Output of `examples/retry_agent/hero_demo.py --n 200` from the release source.",
        "A vs B BLOCK (exit 1), A vs A PASS, divergence after the injected tool_timeout, a "
        "1-minimal reduction to tool_timeout, offline replay REPRODUCED, A vs C PASS.",
    ),
}
DOCKER_LOG = re.compile(r"logs/docker-reproduce-\d{4}-\d{2}-\d{2}\.txt")
DOCKER_LOG_DESCRIPTION = (
    "`reproduce.py --docker` log: source commit, image digest, interpreter, dependency "
    "inventory, both replays, the byte-exact tests and an in-container `reproduce.py --check`.",
    "Its summary table records, on linux/amd64 with no network, whether both committed bundles "
    "REPRODUCED, whether the 18 decisions re-derived byte for byte, and the in-container check.",
)
GENERIC_DESCRIPTION = (
    "A file in the ci-gate-2026-10-06 package with no entry in reproduce.py's table.",
    "Not described: read the file before relying on it.",
)


@dataclass(frozen=True)
class Row:
    step: str
    ok: bool | None  # None: informational, never fails the run
    detail: str


# --------------------------------------------------------------------------- files and hashes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_files() -> list[str]:
    """Package-relative POSIX paths of every evidence file, sorted."""
    found: list[str] = []
    for path in HERE.rglob("*"):
        relative = path.relative_to(HERE)
        if IGNORED_NAMES.intersection(relative.parts) or not path.is_file():
            continue
        name = relative.as_posix()
        if name not in EXCLUDED_FILES:
            found.append(name)
    return sorted(found)


def describe(name: str) -> tuple[str, str]:
    if name in DESCRIPTIONS:
        return DESCRIPTIONS[name]
    if DOCKER_LOG.fullmatch(name):
        return DOCKER_LOG_DESCRIPTION
    return GENERIC_DESCRIPTION


def decision_files() -> list[Path]:
    return sorted(RESULTS.rglob("decision.json"))


def external_evidence() -> list[dict[str, object]]:
    """Repository files the package's claims rest on, by how they are checked."""
    entries: list[dict[str, object]] = []

    def add(path: Path, role: str) -> None:
        entries.append(
            {
                "path": path.relative_to(REPO).as_posix(),
                "sha256": _sha256(path),
                "size": path.stat().st_size,
                "role": role,
            }
        )

    for decision in decision_files():
        add(decision, "decision regeneration: re-derived byte for byte by reproduce.py --check")
    for _, bundle in REPLAYS:
        add(REPO / bundle, "agent replay: replayed unchanged by reproduce.py --docker")
    for report in sorted(RESULTS.glob("ollama-run*.md")):
        add(report, "archival report only: no committed stores, not re-derived")
    return entries


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True, timeout=60
    )
    return completed.stdout.strip()


def _arci_version() -> str:
    try:
        return importlib.metadata.version("agent-reliability-ci")
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def write_index() -> int:
    files = package_files()
    index: dict[str, object] = {
        "schema": "arci.evidence-index.v1",
        "package": PACKAGE,
        "source_commit": _git("rev-parse", "HEAD"),
        "source_commit_note": (
            "Commit checked out when this index was generated; package hashes identify "
            "the indexed files. The release tag identifies the delivered snapshot."
        ),
        "arci_version": _arci_version(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "sha256sums": {"file": "SHA256SUMS", "working_directory": PACKAGE},
        "excluded": [*EXCLUDED_FILES, "__pycache__/", ".DS_Store"],
        "checks": {
            "decision regeneration": "reproduce.py --check (step b), also inside --docker",
            "planner example": "reproduce.py --check (step c)",
            "self-check metrics": "reproduce.py --check --full",
            "agent replay": "reproduce.py --docker (linux/amd64, network none)",
            "archival only": "Ollama reports: cited, not re-derived",
        },
        "files": [
            {
                "path": name,
                "sha256": _sha256(HERE / name),
                "size": (HERE / name).stat().st_size,
                "what": describe(name)[0],
                "proves": describe(name)[1],
            }
            for name in files
        ],
        "external": external_evidence(),
    }
    INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SUMS.write_text("".join(f"{_sha256(HERE / name)}  {name}\n" for name in files), "utf-8")
    external = cast(list[object], index["external"])
    print(f"wrote {INDEX.relative_to(REPO)} ({len(files)} files, {len(external)} external)")
    print(f"wrote {SUMS.relative_to(REPO)}")
    return 0


# --------------------------------------------------------------------------- check steps


def check_sums() -> Row:
    if not SUMS.is_file():
        return Row("SHA256SUMS", False, "SHA256SUMS missing: run --index")
    listed: dict[str, str] = {}
    for number, line in enumerate(SUMS.read_text("utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) [ *](.+)", line)
        if match is None:
            return Row("SHA256SUMS", False, f"line {number} is not sha256sum format")
        listed[match.group(2)] = match.group(1)
    present = package_files()
    problems = [f"unlisted: {name}" for name in present if name not in listed]
    problems += [f"missing: {name}" for name in listed if name not in present]
    problems += [
        f"sha256 differs: {name}"
        for name, digest in listed.items()
        if name in present and _sha256(HERE / name) != digest
    ]
    if problems:
        return Row("SHA256SUMS", False, "; ".join(problems))
    return Row("SHA256SUMS", True, f"{len(listed)} files match; no unlisted file")


def check_external() -> Row:
    step = "index: evidence outside the package"
    if not INDEX.is_file():
        return Row(step, False, "evidence-index.json missing: run --index")
    index = cast(dict[str, object], json.loads(INDEX.read_text("utf-8")))
    entries = cast(list[dict[str, object]], index.get("external", []))
    problems: list[str] = []
    for entry in entries:
        path = REPO / str(entry["path"])
        if not path.is_file():
            problems.append(f"missing: {entry['path']}")
        elif _sha256(path) != entry["sha256"]:
            problems.append(f"sha256 differs: {entry['path']}")
    indexed = {str(entry["path"]) for entry in entries}
    problems += [
        f"not indexed: {path.relative_to(REPO).as_posix()}"
        for path in decision_files()
        if path.relative_to(REPO).as_posix() not in indexed
    ]
    if problems:
        return Row(step, False, "; ".join(problems))
    return Row(step, True, f"{len(entries)} files match (decisions, bundles, archival reports)")


def _scrubbed_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key not in SCRUBBED_ENV}


def _rederive(decision: Path, scratch: Path) -> str | None:
    """None when the committed decision re-derives byte for byte with its exit code."""
    store = decision.parent
    name = store.relative_to(RESULTS).as_posix()
    target = scratch / hashlib.sha256(name.encode()).hexdigest()[:16] / store.name
    target.mkdir(parents=True)
    for record in ("manifest.json", "trials.jsonl"):
        shutil.copyfile(store / record, target / record)
    committed = decision.read_bytes()
    expected_exit = cast(dict[str, object], json.loads(committed)).get("exit_code")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "arci.cli", "gate", str(target)],
            env=_scrubbed_env(),
            capture_output=True,
            timeout=GATE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"{name}: timed out after {GATE_TIMEOUT} s"
    regenerated = target / "decision.json"
    if completed.returncode != expected_exit:
        return f"{name}: exit {completed.returncode}, committed exit_code {expected_exit}"
    if not regenerated.is_file():
        return f"{name}: no decision.json written"
    if regenerated.read_bytes() != committed:
        return f"{name}: bytes differ"
    if decision.read_bytes() != committed:
        return f"{name}: the committed decision changed during the check"
    return None


def check_decisions(scratch: Path) -> Row:
    step = "decision re-derivation"
    decisions = decision_files()
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        failures = [
            failure
            for failure in pool.map(_rederive, decisions, [scratch] * len(decisions))
            if failure is not None
        ]
    if len(decisions) != EXPECTED_DECISIONS:
        failures.insert(0, f"found {len(decisions)} decision.json, expected {EXPECTED_DECISIONS}")
    if failures:
        return Row(step, False, "; ".join(failures))
    return Row(
        step, True, f"{len(decisions)}/{EXPECTED_DECISIONS} byte-identical, exit codes match"
    )


def _plan(output_format: str, committed_name: str, scratch: Path) -> Row:
    step = f"planner {output_format}"
    command = [sys.executable, "-m", "arci.cli", "plan", *PLAN_FLAGS, "--format", output_format]
    try:
        completed = subprocess.run(
            command,
            env=_scrubbed_env(),
            capture_output=True,
            timeout=PLAN_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Row(step, False, f"`arci plan` timed out after {PLAN_TIMEOUT} s")
    errors = completed.stderr.decode("utf-8", "replace") + completed.stdout.decode(
        "utf-8", "replace"
    )
    if completed.returncode != 0 and "invalid choice: 'plan'" in errors:
        return Row(
            step,
            False,
            f"`arci plan` is absent from the installed arci {_arci_version()}; this step is "
            "required and never skipped: install an arci that provides `arci plan` and re-run",
        )
    if completed.returncode != 0:
        tail = " | ".join(errors.strip().splitlines()[-3:])
        return Row(step, False, f"`arci plan` exited {completed.returncode}: {tail}")
    regenerated = scratch / committed_name
    regenerated.write_bytes(completed.stdout)
    if regenerated.read_bytes() != (METRICS / committed_name).read_bytes():
        return Row(step, False, f"metrics/{committed_name}: bytes differ")
    return Row(step, True, f"metrics/{committed_name} byte-identical")


def check_planner(scratch: Path) -> list[Row]:
    with ThreadPoolExecutor(max_workers=len(PLAN_OUTPUTS)) as pool:
        futures = [pool.submit(_plan, fmt, name, scratch) for fmt, name in PLAN_OUTPUTS]
        return [future.result() for future in futures]


def _selfcheck(method: str, scratch: Path) -> Row:
    step = f"selfcheck {method}"
    regenerated = scratch / f"selfcheck-{method}.json"
    command = [
        sys.executable,
        str(REPO / "bench" / "selfcheck.py"),
        "--method",
        method,
        "--json",
        str(regenerated),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO,
            env={**_scrubbed_env(), "PYTHONPATH": str(REPO)},
            capture_output=True,
            timeout=SELFCHECK_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Row(step, False, f"timed out after {SELFCHECK_TIMEOUT} s")
    if completed.returncode != 0 or not regenerated.is_file():
        return Row(step, False, f"bench/selfcheck.py exited {completed.returncode}")
    committed = METRICS / regenerated.name
    if json.loads(regenerated.read_bytes()) != json.loads(committed.read_bytes()):
        return Row(step, False, f"metrics/{committed.name}: values differ")
    identical = regenerated.read_bytes() == committed.read_bytes()
    return Row(
        step,
        True,
        f"metrics/{committed.name}: values equal exactly"
        + ("; bytes identical" if identical else "; bytes differ (values equal)"),
    )


def check_selfcheck(scratch: Path) -> list[Row]:
    return [_selfcheck(method, scratch) for method in SELFCHECK_METHODS]


def check_summarize() -> Row:
    step = "guardrail summarize.py --check"
    try:
        completed = subprocess.run(
            [sys.executable, str(RESULTS / "guardrail" / "summarize.py"), "--check"],
            cwd=REPO,
            env=_scrubbed_env(),
            capture_output=True,
            timeout=SUMMARIZE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Row(step, False, f"timed out after {SUMMARIZE_TIMEOUT} s")
    if completed.returncode != 0:
        tail = completed.stderr.decode("utf-8", "replace").strip().splitlines()[-1:]
        return Row(step, False, f"exit {completed.returncode}: {' '.join(tail)}")
    return Row(step, True, "README.md and metrics.json are current")


def report_placeholders() -> list[str]:
    return [match.group(0) for match in PLACEHOLDER.finditer(REPORT.read_text("utf-8"))]


def placeholder_family(placeholder: str) -> str | None:
    match = PLACEHOLDER_FAMILY.match(placeholder[2:-2])
    return match.group(1) if match else None


def check_placeholders(strict: bool) -> Row:
    step = "REPORT.md placeholders"
    found = report_placeholders()
    families = [placeholder_family(item) for item in found]
    unknown = [
        item
        for item, family in zip(found, families, strict=True)
        if family not in ALLOWED_PLACEHOLDER_FAMILIES
    ]
    counts = ", ".join(
        f"{family} {families.count(family)}"
        for family in ALLOWED_PLACEHOLDER_FAMILIES
        if family in families
    )
    if unknown:
        return Row(step, False, f"not an allowed family: {'; '.join(unknown)}")
    if strict and found:
        return Row(step, False, f"--strict: {len(found)} left ({counts})")
    if found:
        return Row(step, None, f"{len(found)} tolerated without --strict ({counts})")
    return Row(step, True, "none left")


def print_table(rows: Sequence[Row]) -> None:
    width = max(len(row.step) for row in rows)
    print(f"{'step':<{width}}  result  detail")
    for row in rows:
        result = "info" if row.ok is None else "ok" if row.ok else "FAIL"
        print(f"{row.step:<{width}}  {result:<6}  {row.detail}")
    failed = sum(1 for row in rows if row.ok is False)
    print(f"{'overall':<{width}}  {'FAIL' if failed else 'ok':<6}  {failed} failed of {len(rows)}")


def check(full: bool, strict: bool) -> int:
    rows: list[Row] = []
    with tempfile.TemporaryDirectory(prefix="arci-reproduce-") as temporary:
        scratch = Path(temporary)
        rows.append(check_sums())
        rows.append(check_external())
        with ThreadPoolExecutor(max_workers=2) as pool:
            planner = pool.submit(check_planner, scratch)
            rows.append(check_decisions(scratch))
            rows.extend(planner.result())
        if full:
            rows.extend(check_selfcheck(scratch))
            rows.append(check_summarize())
        rows.append(check_placeholders(strict))
    print_table(rows)
    return 1 if any(row.ok is False for row in rows) else 0


# --------------------------------------------------------------------------- docker


def _run_logged(
    command: Sequence[str], log: Callable[[str], None], *, mask: dict[str, str] | None = None
) -> tuple[int, str]:
    shown = " ".join(command)
    for text, replacement in (mask or {}).items():
        shown = shown.replace(text, replacement)
    log(f"$ {shown}")
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=7200,
    )
    output = (completed.stdout + completed.stderr).rstrip("\n")
    if output:
        log(output)
    log(f"[exit {completed.returncode}]")
    return completed.returncode, completed.stdout + completed.stderr


def _export_source(target: Path) -> list[str]:
    """Copy tracked and untracked-but-not-ignored files; return `git status --short` lines."""
    names = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "-co", "--exclude-standard"],
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout.split(b"\0")
    for raw in names:
        if not raw:
            continue
        source = REPO / raw.decode("utf-8")
        if not source.is_file() or IGNORED_NAMES.intersection(Path(raw.decode()).parts):
            continue
        destination = target / raw.decode("utf-8")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)
    status = _git("status", "--short", "--untracked-files=all")
    return status.splitlines()


def _section(output: str, header: str) -> str:
    """Text after `== header` up to the next `== ` line."""
    match = re.search(rf"^== {re.escape(header)}\n(.*?)(?=^== |\Z)", output, re.M | re.S)
    return match.group(1) if match else ""


def _stage_two_script() -> str:
    replays = "\n".join(
        f"echo '== replay {label}'; .venv/bin/arci replay {bundle}; echo \"exit $?\""
        for label, bundle in REPLAYS
    )
    return f"""
set +e
mkdir -p {Path(SEALED_GUARDRAIL_ROOT).parent}
ln -s {SEALED_JEV_ROOT} {SEALED_GUARDRAIL_ROOT}
cd {SEALED_JEV_ROOT} && export PYTHONPATH=$PWD
{replays}
echo '== byte-exact tests'
.venv/bin/python -m pytest -p no:cacheprovider {" ".join(REDERIVATION_TESTS)} -k byte_for_byte
echo "exit $?"
echo '== reproduce.py --check'
.venv/bin/python {PACKAGE}/reproduce.py --check
echo "exit $?"
"""


def docker() -> int:
    date = datetime.date.today().isoformat()
    log_path = LOGS / f"docker-reproduce-{date}.txt"
    lines: list[str] = []

    def log(text: str) -> None:
        lines.append(text)
        print(text, flush=True)

    rows: list[Row] = []
    log(f"# reproduce.py --docker, {date}")
    log(f"host: {platform.platform()}; python {platform.python_version()}")
    log(f"source commit (HEAD): {_git('rev-parse', 'HEAD')}")
    _, version = _run_logged(["docker", "version", "--format", "{{.Server.Version}}"], log)
    with tempfile.TemporaryDirectory(prefix="arci-docker-src-") as temporary:
        source = Path(temporary) / "src"
        source.mkdir()
        status = _export_source(source)
        log("uncommitted changes copied into the container (git status --short):")
        log("\n".join(f"  {line}" for line in status) if status else "  none")
        image = _run_logged(["docker", "image", "inspect", DOCKER_IMAGE, "--format", "x"], log)[0]
        if image != 0:
            _run_logged(["docker", "pull", "--platform", DOCKER_PLATFORM, DOCKER_IMAGE], log)
        code, digest = _run_logged(
            ["docker", "image", "inspect", DOCKER_IMAGE, "--format", "{{index .RepoDigests 0}}"],
            log,
        )
        digest = digest.strip() if code == 0 else "unknown"
        log(f"image digest: {digest}")
        _run_logged(["docker", "volume", "rm", "-f", DOCKER_VOLUME], log)
        _run_logged(["docker", "volume", "create", DOCKER_VOLUME], log)
        log("== stage 1: install the pinned source into the sealed Linux path (network on)")
        stage_one = (
            f"set -e; rm -rf {SEALED_JEV_ROOT}; cp -r /w {SEALED_JEV_ROOT}; "
            f"cd {SEALED_JEV_ROOT} && rm -rf .venv && python -m venv .venv && "
            f".venv/bin/pip install -q --no-cache-dir --disable-pip-version-check . "
            f"'{PYTEST_PIN}'; .venv/bin/python -VV; uname -m; "
            f"echo 'dependency inventory (pip freeze):'; .venv/bin/pip freeze --all"
        )
        stage_one_code, _ = _run_logged(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                DOCKER_PLATFORM,
                "-v",
                f"{source}:/w:ro",
                "-v",
                f"{DOCKER_VOLUME}:/home/user",
                DOCKER_IMAGE,
                "bash",
                "-lc",
                stage_one,
            ],
            log,
            mask={str(source): "<exported source>"},
        )
    rows.append(Row("stage 1 install", stage_one_code == 0, f"exit {stage_one_code}"))
    log("== stage 2: replay and re-derive (network none)")
    _, output = _run_logged(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            DOCKER_PLATFORM,
            "--network",
            "none",
            "-v",
            f"{DOCKER_VOLUME}:/home/user",
            DOCKER_IMAGE,
            "bash",
            "-l",
            "-c",
            _stage_two_script(),
        ],
        log,
    )
    for label, bundle in REPLAYS:
        section = _section(output, f"replay {label}")
        ok = REPRODUCED_LINE in section and re.search(r"^exit 0$", section, re.M) is not None
        line = next((x for x in section.splitlines() if x.startswith("REPRODUCED")), "none")
        rows.append(Row(f"replay {label}", ok, f"{line} ({bundle})"))
    tests = _section(output, "byte-exact tests")
    passed = PYTEST_PASS_LINE.search(tests)
    rows.append(
        Row(
            "18 byte-exact tests",
            passed is not None and re.search(r"^exit 0$", tests, re.M) is not None,
            passed.group(0).strip() if passed else "no '18 passed' line",
        )
    )
    inner = _section(output, "reproduce.py --check")
    failing = [
        x
        for x in inner.splitlines()
        if re.match(r"^\S.*\s{2}FAIL\s{2}", x) and not x.startswith("overall")
    ]
    rows.append(
        Row(
            "in-container --check",
            re.search(r"^exit 0$", inner, re.M) is not None,
            "all rows ok" if not failing else "; ".join(re.sub(r"\s{2,}", " ", x) for x in failing),
        )
    )
    rows.append(Row("image digest", None, digest))
    rows.append(Row("docker server", None, version.strip()))
    log("== summary")
    width = max(len(row.step) for row in rows)
    for row in rows:
        result = "info" if row.ok is None else "ok" if row.ok else "FAIL"
        log(f"{row.step:<{width}}  {result:<6}  {row.detail}")
    failed = any(row.ok is False for row in rows)
    log(f"overall: {'FAIL' if failed else 'ok'}")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {log_path.relative_to(REPO)}; re-run --index to cover it")
    return 1 if failed else 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--index", action="store_true", help="write evidence-index.json, SHA256SUMS")
    mode.add_argument("--check", action="store_true", help="verify and re-derive (the default)")
    mode.add_argument("--docker", action="store_true", help="linux/amd64 two-stage recipe")
    parser.add_argument("--full", action="store_true", help="with --check: self-checks too")
    parser.add_argument("--strict", action="store_true", help="with --check: no placeholders")
    args = parser.parse_args(None if argv is None else list(argv))
    if (args.full or args.strict) and (args.index or args.docker):
        parser.error("--full and --strict apply to --check only")
    if args.index:
        return write_index()
    if args.docker:
        return docker()
    return check(full=bool(args.full), strict=bool(args.strict))


if __name__ == "__main__":
    sys.exit(main())
