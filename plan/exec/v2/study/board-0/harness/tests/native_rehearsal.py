"""Run a disposable, locally registered Board-0 study through the released live path."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import LIST, NOTE, ROOT, lines, models, need, read, schedule
from inputs import sources


@contextmanager
def step(name: str) -> Generator[None, None, None]:
    print(name, flush=True)
    try:
        yield
    except (Exception, KeyboardInterrupt) as exc:
        raise RuntimeError(f"{name}: {exc}") from exc


@contextmanager
def fake_server(study: Path, python: str, env: dict[str, str]) -> Generator[None, None, None]:
    log = study.parent / "fake-ollama.log"
    with (
        log.open("w") as errors,
        subprocess.Popen(
            [python, "-PB", "harness/tests/fake_ollama.py"],
            cwd=study,
            env=env,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True,
        ) as proc,
    ):
        try:
            # Only our child can signal readiness. Never probe a pre-existing listener.
            assert proc.stdout
            if proc.stdout.readline() != "READY\n":
                raise RuntimeError(f"fake Ollama startup failed: {log.read_text()}")
            yield
            need(proc.poll() is None, "fake Ollama exited during rehearsal")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def register(study: Path, claims: Path, env: dict[str, str], amendment: int) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=study, env=env, text=True, stdin=subprocess.DEVNULL
        ).strip()

    branch = "v2/phase0"
    remote = study.parent / "remote.git"
    if amendment == 1:
        git("init", "--bare", "--template=", str(remote))
        git("init", "--template=", "-b", branch)
        git("remote", "add", "origin", str(remote))
    git("add", "--", *sources(), LIST, NOTE, "clean", "runs")
    git(
        "-c",
        "user.name=Board Rehearsal",
        "-c",
        "user.email=board@example.invalid",
        "commit",
        "-m",
        f"Register Board-0 rehearsal amendment {amendment}",
    )
    git("push", "origin", branch)
    receipt = git("ls-remote", "--exit-code", "origin", f"refs/heads/{branch}").split()
    need(receipt == [git("rev-parse", "HEAD"), f"refs/heads/{branch}"], "local push receipt")
    (claims / "push-receipt.txt").write_text(" ".join(receipt) + "\n")


def rehearse(work: Path) -> None:
    study = work / "study"
    claims = work / "claims"
    envdir = Path(os.environ.get("BOARD0_ENV") or "/Users/Shared/arci-reply0/env").absolute()
    bindir = envdir / "py/bin"
    python = str(bindir / "python")
    # Pass only the selected release and copied harness to all launcher descendants.
    env = {
        "BOARD0_ENV": str(envdir),
        "BOARD0_CLAIMS": str(claims),
        "PATH": f"{bindir}:/usr/bin:/bin",
        "PYTHONPATH": str(study / "harness"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "TMPDIR": str(work / "tmp"),
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ALLOW_PROTOCOL": "file",
    }

    def launcher(*args: str, rejection: str | None = None) -> str:
        result = subprocess.run(
            [python, "-PB", "harness/launcher.py", *args],
            cwd=study,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        if rejection is None:
            need(result.returncode == 0, result.stderr or result.stdout)
        else:
            need(
                result.returncode != 0 and result.stderr.rstrip().splitlines()[-1:] == [rejection],
                f"expected {rejection!r}, got exit {result.returncode}: {result.stderr}",
            )
        return result.stdout

    with step("Copy registered inputs"):
        need(Path(python).is_file(), f"missing released interpreter: {python}")
        claims.mkdir(mode=0o700)
        (work / "tmp").mkdir()
        for name in sources():
            destination = study / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        slots = models(study / "models.json")

    with fake_server(study, python, env):
        with step("Prepare and register with local origin"):
            launcher("prepare")
            (study / LIST).write_text(launcher("digests"))
            register(study, claims, env, 1)
            launcher("check")

        for model in slots:
            run = model["pin"]
            with step(run):
                passed = model != slots[-1]
                launcher(
                    "real",
                    run,
                    rejection=None
                    if passed
                    else "pin.PinFailed: pin threshold or empty delivery failed",
                )
                pin = read(study / "pins" / (run + ".json"))
                need(
                    pin["ok"] is passed
                    and pin["passed"] == (20 if passed else 0)
                    and len(pin["delivery"]) == 2
                    and all(p["passed"] for p in pin["delivery"])
                    and read(claims / run / "finished.json")["ok"] is passed,
                    "unexpected probe results",
                )

        with step("Pin S1 and refuse S2"):
            launcher("real", "board0-pin2-S1")
            launcher("real", "board0-pin2-S2", rejection="ValueError: spare S2 not required")
            need(not (claims / "board0-pin2-S2").exists(), "refusal created a claim")

        with step("Apply and push amendment 2"):
            launcher("roster")
            slots = models(study / "models.json")
            spare = read(study / "models.json")["spares"][0]
            need(slots[-1] == spare | {"slot": "M5"}, "last slot did not receive S1")
            launcher("prepare")
            (study / NOTE).write_text(launcher("descriptor-digests"))
            (study / LIST).write_text(launcher("digests"))
            register(study, claims, env, 2)
            launcher("check")

        report_rows = []
        # M2 through M4 must finish before the substituted M5 can be claimed.
        for run in (r for r in schedule(slots) if "-d1-" in r):
            with step(run):
                launcher("real", run)
                need(read(claims / run / "finished.json")["ok"] is True, "unfinished run")
                if run.endswith("-clean"):
                    clean_dir = study / "clean"
                    clean = read(clean_dir / (run + ".json"))
                    trials = [
                        trial
                        for path in (clean_dir / run).glob("*/trials.jsonl")
                        for trial in lines(path)
                    ]
                    need(
                        clean["families"] == {"orders": 8, "calendar": 8}
                        and clean["rated"]
                        and len(trials) == 32
                        and all(trial["outcome"] == "PASS" for trial in trials),
                        "clean rating",
                    )
                else:
                    dest = study / "runs" / run
                    audit = read(dest / "audit.json")
                    verdict = read(dest / "decision.json")["verdict"]
                    need(
                        audit["model_digest"] == slots[int(run.split("-")[2][1:]) - 1]["digest"]
                        and audit["transport"] == "native Ollama"
                        and audit["counts_agree"]
                        and audit["verdict"] == verdict
                        and verdict in ("BLOCK", "PASS", "INCONCLUSIVE")
                        and read(dest / "count_a.json")["signs"]["errored"] == 0,
                        "measured suite verdict or evidence",
                    )
                    report_rows.append(
                        (run.split("-")[2], f"{verdict} at round {audit['stopping_round']}.")
                    )

        with step("Render and check report"):
            report = launcher("report")
            (study / "result.md").write_text(report)
            for slot, verdict_line in report_rows:
                section = report.split(f"## {slot} · day 1 · ", 1)[1].split("\n## ", 1)[0]
                need("Status: rated." in section and verdict_line in section, f"report for {slot}")


def main() -> int:
    os.umask(0o077)
    work = Path(tempfile.mkdtemp(prefix="board0-native-", dir="/private/tmp")).resolve()
    try:
        rehearse(work)
        shutil.rmtree(work)
    except (Exception, KeyboardInterrupt) as exc:
        print(f"FAIL Board-0 native rehearsal: {exc}\nRetained {work}", file=sys.stderr)
        return 1
    print("PASS Board-0 native rehearsal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
