"""Grade a finished export against a second, independently exported parent."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PYTHON = Path("/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python")
AGENT_PYTHON = Path("/Users/ajay/Developer/.arci-worktrees/codex-effort-agent-env/bin/python")
# Offline fixtures opt out explicitly when nested sandboxing is unavailable.
ISOLATE_GRADER = True
Outcome = Literal["pass", "fail", "error"]
INFRA_SECONDS = 60


class Hidden(TypedDict):
    path: str
    node_ids: list[str]
    preservation: NotRequired[list[str]]
    supplement: NotRequired[str]


class Ticket(TypedDict):
    id: str
    task: str
    pre_fix_commit: str
    fix_commit: str
    allowed_paths: list[str]
    visible_tests: list[str]
    reference_hunk: NotRequired[dict[str, str]]
    visible_cases: int
    hidden_test: Hidden


@dataclass(frozen=True)
class Grade:
    outcome: Outcome
    reason: str
    diff_sha256: str | None = None


def tickets() -> list[Ticket]:
    return [json.loads(p.read_bytes()) for p in sorted((HERE / "tickets").glob("*.json"))]


def bounded(
    argv: list[str],
    cwd: Path,
    *,
    seconds: float | None = None,
    env: dict[str, str] | None = None,
    data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Keep pipes inherited by helpers (including SSH) out of the timeout path."""
    with (
        tempfile.TemporaryFile() as source,
        tempfile.TemporaryFile() as output,
        tempfile.TemporaryFile() as errors,
    ):
        if data is not None:
            source.write(data)
            source.seek(0)
        with subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(os.environ if env is None else env, GIT_TERMINAL_PROMPT="0"),
            stdin=source,
            stdout=output,
            stderr=errors,
            start_new_session=True,
        ) as proc:
            try:
                rc = proc.wait(timeout=INFRA_SECONDS if seconds is None else seconds)
            finally:
                with suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
        output.seek(0)
        errors.seek(0)
        return subprocess.CompletedProcess(argv, rc, output.read(), errors.read())


def git(*args: str, cwd: Path = REPO) -> bytes:
    proc = bounded(["/usr/bin/git", *args], cwd)
    proc.check_returncode()
    return proc.stdout


def blob(rev: str, path: str) -> bytes:
    return git("show", f"{rev}:{path}")


def export(rev: str, tree: Path) -> None:
    tree.mkdir()
    archive = git("archive", "--format=tar", rev)
    bounded(["/usr/bin/tar", "-xf", "-"], tree, data=archive).check_returncode()
    if (tree / ".git").exists():
        raise RuntimeError("invalid commit export")


def outside(root: Path) -> Path:
    root = root.resolve()
    if root.is_relative_to(REPO) or REPO.is_relative_to(root):
        raise ValueError("work root must be separate from the checkout")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def run_process(
    argv: list[str],
    cwd: Path,
    env: dict[str, str],
    log: Path,
    seconds: float,
    *,
    stderr: Path | None = None,
) -> int | None:
    """A timeout kills the process group, including child test runners."""
    with (
        os.fdopen(os.open(log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream,
        stderr.open("xb") if stderr else nullcontext() as diagnostics,
        tempfile.TemporaryFile() if stderr is None else nullcontext() as spool,
        subprocess.Popen(
            argv,
            cwd=cwd,
            env=dict(env, GIT_TERMINAL_PROMPT="0"),
            stdin=subprocess.DEVNULL,
            stdout=spool if spool is not None else stream,
            stderr=diagnostics if diagnostics else subprocess.STDOUT,
            start_new_session=True,
        ) as proc,
    ):
        try:
            return proc.wait(timeout=max(0, seconds))
        except subprocess.TimeoutExpired:
            return None
        finally:
            # Also reap descendants a parent may have left on a normal exit.
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGKILL)
            if spool is not None:
                # The grader child inherits only its own spool, never a campaign evidence fd.
                spool.seek(0)
                shutil.copyfileobj(spool, stream)


def test_nodes(
    tree: Path,
    nodes: list[str],
    expected: int,
    work: Path,
    out: Path,
    label: str,
    seconds: float = 90,
) -> tuple[Outcome, str]:
    """Use a new process per suite. Reject skips, empty collection and early exits."""
    with tempfile.TemporaryDirectory(dir=work) as scratch_name:
        scratch = Path(scratch_name)
        xml = scratch / "cases.xml"
        env = {
            "HOME": str(scratch),
            "TMPDIR": str(scratch),
            "PATH": str(AGENT_PYTHON.parent) + ":/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(tree / "src"),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONNOUSERSITE": "1",
            "LC_ALL": "C",
            "GIT_CEILING_DIRECTORIES": str(tree.parent),
        }
        runner: list[str] = []
        if ISOLATE_GRADER:
            # The submitted module runs in pytest. Give the whole process tree write
            # access only to scratch and read access only to tests, source and runtimes.
            paths = (tree, scratch, AGENT_PYTHON.parent.parent, AGENT_PYTHON.resolve().parents[1])
            allow = " ".join(f"(subpath {json.dumps(str(p.resolve()))})" for p in paths)
            profile = (
                "(version 1)(allow default)(deny network*)(deny file-read-data)(deny file-write*)"
                '(allow file-read-data (subpath "/System/Library") '
                '(subpath "/usr/lib") (subpath "/usr/bin") '
                '(subpath "/usr/share") (subpath "/usr/libexec") (subpath "/Library/Apple") '
                '(literal "/") (subpath "/bin") (subpath "/sbin") (subpath "/private/etc") (subpath "/dev") '
                + allow
                + ")"
                + f'(allow file-write* (literal "/dev/null") (subpath {json.dumps(str(scratch))}))'
            )
            runner = ["/usr/bin/sandbox-exec", "-p", profile]
        rc = run_process(
            [
                *runner,
                str(AGENT_PYTHON),
                "-m",
                "pytest",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
                "-q",
                "--tb=short",
                f"--junitxml={xml}",
                *nodes,
            ],
            tree,
            env,
            out / f"{label}.log",
            seconds,
        )
        issue = classify_cases(xml, nodes, expected, rc)
        return issue[0], f"{label}: {issue[1]}"


def classify_cases(
    xml: Path, nodes: list[str], expected: int, rc: int | None
) -> tuple[Outcome, str]:
    if rc is None:
        return "error", "test timeout"
    if rc not in (0, 1):
        return "error", f"pytest exit {rc}"
    try:
        with os.fdopen(os.open(xml, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                return "error", "malformed pytest case file"
            root = ET.parse(stream).getroot()
    except FileNotFoundError:
        return "error", "missing pytest case results"
    except (ET.ParseError, OSError):
        return "error", "malformed pytest case results"
    if root.tag not in ("testsuite", "testsuites"):
        return "error", "malformed pytest suite"
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    cases: list[ET.Element] = []
    for suite in suites:
        suite_cases = suite.findall("testcase")
        totals = {
            "tests": len(suite_cases),
            **{
                count: sum(case.find(tag) is not None for case in suite_cases)
                for count, tag in (
                    ("failures", "failure"),
                    ("errors", "error"),
                    ("skipped", "skipped"),
                )
            },
        }
        if any(suite.get(k, str(n)) != str(n) for k, n in totals.items()):
            return "error", "malformed pytest suite counts"
        cases.extend(suite_cases)
    # JUnit encodes a node's module/class separately from its parameterized name.
    expected_ids: list[tuple[str, str]] = []
    for node in nodes:
        module, tail = node.split("::", 1)
        symbol, bracket, params = tail.partition("[")
        prefix, _, name = symbol.rpartition("::")
        name += bracket + params
        owner = module.removesuffix(".py").replace("/", ".")
        expected_ids.append((owner + ("." + prefix.replace("::", ".") if prefix else ""), name))
    actual = [(c.get("classname", ""), c.get("name", "")) for c in cases]
    if len(cases) != expected or sorted(expected_ids) != sorted(actual):
        return "error", "unexpected pytest case identities"
    children = [child.tag for case in cases for child in case]
    if rc == 0 and not children:
        return "pass", f"{len(cases)} passed"
    if rc == 1 and children and set(children) == {"failure"}:
        return "fail", "pytest exit 1"
    return "error", f"inconsistent or incomplete pytest results (exit {rc})"


def reference_source(ticket: Ticket, name: str) -> bytes:
    fixed = blob(ticket["fix_commit"], name)
    hunk = ticket.get("reference_hunk")
    if not hunk or hunk["path"] != name:
        return fixed
    parent = blob(ticket["pre_fix_commit"], name)
    before, after = hunk["before"].encode(), hunk["after"].encode()
    if parent.count(before) != 1 or fixed.count(after) != 1:
        raise ValueError("reference hunk differs from historical files")
    return parent.replace(before, after)


def install_hidden(tree: Path, ticket: Ticket) -> None:
    hidden = ticket["hidden_test"]
    name = hidden["path"]
    path = tree / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = blob(ticket["fix_commit"], name)
    if addition := hidden.get("supplement"):
        data += b"\n\n" + (HERE / "hidden" / addition).read_bytes()
    path.write_bytes(data)


def checked_suite(
    ticket: Ticket, tree: Path, work: Path, out: Path, label: str, seconds: float
) -> tuple[Outcome, str]:
    if label == "visible":
        nodes = ticket["visible_tests"]
    else:
        install_hidden(tree, ticket)
        hidden = ticket["hidden_test"]
        nodes = hidden["node_ids"] + hidden.get("preservation", [])
    count = len(nodes)
    outcome, why = test_nodes(tree, nodes, count, work, out, label, seconds)
    if outcome != "error":
        return outcome, why
    # Fresh parent plus reference/submitted source. Controls each receive exactly
    # the original stage allowance, even if the initial process timed out.
    evidence = [why]
    for variant in ("control", "repeat"):
        clean = work / (label + "-" + variant)
        export(ticket["pre_fix_commit"], clean)
        for name in ticket["allowed_paths"]:
            if variant == "control":
                (clean / name).write_bytes(reference_source(ticket, name))
            elif (tree / name).is_file():
                (clean / name).write_bytes((tree / name).read_bytes())
            else:
                (clean / name).unlink(missing_ok=True)
        if label == "hidden":
            install_hidden(clean, ticket)
        status, detail = test_nodes(clean, nodes, count, work, out, label + "-" + variant, seconds)
        evidence.append(detail)
        if variant == "control" and status != "pass":
            return "error", ", ".join(evidence)
    reproduced = detail.partition(": ")[2] == why.partition(": ")[2]
    return ("fail" if reproduced else "error"), ", ".join(evidence)


def is_allowed(path: str, ticket: Ticket) -> bool:
    parts = Path(path).parts
    return (
        path in ticket["allowed_paths"]
        and parts[:2] == ("src", "arci")
        and not any(x in ("test", "tests") for x in parts)
        and not parts[-1].startswith("test_")
        and not parts[-1].endswith("_test.py")
    )


def inventory(tree: Path) -> dict[str, tuple[int, bytes]]:
    entries: dict[str, tuple[int, bytes]] = {}

    def visit(directory: Path) -> None:
        for p in directory.iterdir():
            rel = p.relative_to(tree).as_posix()
            info = p.lstat()
            mode = info.st_mode
            if stat.S_ISDIR(mode):
                entries[rel] = (mode, b"")
                visit(p)
            elif stat.S_ISREG(mode) and info.st_nlink == 1:
                with p.open("rb") as f:
                    entries[rel] = (mode, hashlib.file_digest(f, "sha256").digest())
            elif stat.S_ISLNK(mode):
                entries[rel] = (mode, os.fsencode(os.readlink(p)))
            else:
                raise ValueError(f"unsupported file type or hard link: {rel}")

    if tree.is_symlink() or not tree.is_dir():
        raise ValueError("trial replaced the export root")
    visit(tree)
    return entries


def grade(ticket: Ticket, tree: Path, out: Path, *, agent_failure: Grade | None = None) -> Grade:
    """Capture the submitted diff even for timeout/refusal; neither can earn a pass."""
    work = tree.parent
    with tempfile.TemporaryDirectory(dir=work) as fresh:
        # Diff operands have exactly two path components, including their common parent.
        clean = Path(fresh) / "clean"
        export(ticket["pre_fix_commit"], clean)
        original = inventory(clean)
        try:
            updated = inventory(tree)
        except (ValueError, PermissionError) as exc:
            return agent_failure or Grade("fail", str(exc))
        changed = sorted(
            p for p in original.keys() | updated.keys() if original.get(p) != updated.get(p)
        )
        # no-index considers ignored/untracked files too. No index or Git tree is written.
        # Generate operands with equal depth, independently of absolute work-root names.
        with tempfile.TemporaryDirectory(dir=work) as pair_name:
            pair = Path(pair_name)
            tree.rename(pair / "edited")
            clean.rename(pair / "clean")
            try:
                proc = bounded(
                    [
                        "/usr/bin/git",
                        "-c",
                        "core.filemode=true",
                        "diff",
                        "--no-index",
                        "--no-ext-diff",
                        "--no-textconv",
                        "--binary",
                        "--no-renames",
                        "--src-prefix=a/",
                        "--dst-prefix=b/",
                        "--",
                        "clean",
                        "edited",
                    ],
                    cwd=pair,
                )
            finally:
                (pair / "edited").rename(tree)
                (pair / "clean").rename(clean)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"diff failed: {proc.stderr.decode(errors='replace')}")
        patch = proc.stdout
        (out / "change.patch").write_bytes(patch)
        digest = hashlib.sha256(patch).hexdigest()
        if agent_failure:
            return Grade(agent_failure.outcome, agent_failure.reason, digest)
        if not changed or not patch:
            return Grade("fail", "empty diff or unrepresentable change", digest)
        for p in changed:
            if not is_allowed(p, ticket):
                return Grade("fail", f"path outside allowed source: {p}", digest)
            if p in updated and not stat.S_ISREG(updated[p][0]):
                return Grade("fail", f"expected a regular source edit: {p}", digest)
        applied = bounded(
            ["/usr/bin/git", "apply", "--whitespace=nowarn", "-p2", "-"],
            cwd=clean,
            data=patch,
        )
        if applied.returncode:
            return Grade("fail", "diff did not apply to the clean parent", digest)
        for name in changed:
            path = clean / name
            if name not in updated and not path.exists():
                continue
            if not path.is_file() or name not in updated:
                return Grade("fail", "applied files differ from submission", digest)
            actual = (path.stat().st_mode, hashlib.sha256(path.read_bytes()).digest())
            if actual != updated[name]:
                return Grade("fail", "applied mode or bytes differ from submission", digest)
        start = time.monotonic()
        # Run parent tests before installing the new file: some nodes share a path.
        result, visible = checked_suite(ticket, clean, work, out, "visible", 90)
        if result != "pass":
            return Grade(result, visible, digest)
        remaining = 90 - (time.monotonic() - start)
        if remaining <= 0:
            return Grade(
                "error",
                visible + ", test budget exhausted",
                digest,
            )
        hidden_result, hidden = checked_suite(ticket, clean, work, out, "hidden", remaining)
        outcomes = (result, hidden_result)
        final = "error" if "error" in outcomes else "fail" if "fail" in outcomes else "pass"
        return Grade(final, visible + ", " + hidden, digest)
