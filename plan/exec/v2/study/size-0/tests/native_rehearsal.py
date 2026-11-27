"""Exercise the native shell launcher against only the fake server we own."""

import argparse
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from claims import schedule  # noqa: E402
from processes import group_alive, start_time  # noqa: E402
from records import rows  # noqa: E402


def until(predicate: Callable[[], bool], timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise RuntimeError("native rehearsal deadline")
        time.sleep(0.05)


def production_admission(temp: Path, control: Path) -> None:
    repo = temp / "repo"
    study = repo / "plan/exec/v2/study/size-0"
    shutil.copytree(
        ROOT,
        study,
        ignore=shutil.ignore_patterns("prepared", "claims", "models.json", "__pycache__"),
    )
    claims, board = temp / "production-claims", temp / "production-board"
    claims.mkdir()
    board.mkdir()
    (board / "suite.lock").touch()
    # Relocate only the compiled-in host locations in the disposable checkout.
    # The wrapper still unsets overrides and verifies blobs before Python imports.
    for name in ("run-size0.sh", "claims.py"):
        path = study / name
        path.write_text(
            path.read_text()
            .replace("/private/var/tmp/arci-size0-claims", str(claims))
            .replace("/private/var/tmp/arci-board0-claims", str(board))
        )
    release = temp / ".arci-worktrees"
    release.mkdir()
    (release / "run4-env").symlink_to(Path(sys.executable).parent.parent, target_is_directory=True)
    shutil.copyfile(study / "models.example.json", study / "models.json")
    (study / "PREREGISTRATION-size-0.draft.md").write_text(
        "Disposable native rehearsal registration.\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "SIZE0_"))}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_NAME="Fixture",
        GIT_COMMITTER_NAME="Fixture",
        GIT_AUTHOR_EMAIL="fixture@example.invalid",
        GIT_COMMITTER_EMAIL="fixture@example.invalid",
    )
    cli = ["sh", str(study / "run-size0.sh")]

    def call(argv: list[str], error: str | None = None) -> str:
        result = subprocess.run(
            argv, cwd=study, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL
        )
        if error is None:
            assert result.returncode == 0, result.stderr
        else:
            assert result.returncode != 0 and error in result.stderr, result.stderr
        return result.stdout.strip()

    call([*cli, "prepare"])
    git = ["git", "-C", str(repo)]
    call([*git, "init", "-q", "--template=", "-b", "v2/phase0"])
    call([*git, "add", "-f", "."])
    call([*git, "commit", "-qm", "native fixture"])
    commit = call([*git, "rev-parse", "HEAD"])
    call([*git, "update-ref", "refs/remotes/origin/v2/phase0", commit])
    (claims / "push-receipt.txt").write_text(commit + " refs/heads/v2/phase0\n")
    call([*cli, "check"])
    first = schedule(False)[0]
    blob = study / "prepared" / (first + ".yaml")
    original = blob.read_bytes()
    blob.write_bytes(original + b" ")
    call([*cli, "real", first], "upstream input differs")
    assert not (claims / first).exists()
    blob.write_bytes(original)
    call([*cli, "preflight", "q2"])
    work = claims / first
    (control / "hold-worker").touch()
    with subprocess.Popen(
        [*cli, "real", first], cwd=study, env=env, stdin=subprocess.DEVNULL
    ) as launcher:
        try:
            until(lambda: (control / "worker-in-chat").is_file() or launcher.poll() is not None)
            assert launcher.poll() is None
            assert (work / "arci.log").read_bytes()
            execution = json.loads((work / "execution.json").read_bytes())
            groups = [json.loads(p.read_bytes()) for p in (work / "groups").glob("*.json")]
            assert any(group_alive(g["pid"], g["start_time"]) for g in groups)
            # Losing the outer launcher must leave the supervisor owning both locks.
            launcher.kill()
            launcher.wait(timeout=10)
            for lock in (claims / "suite.lock", board / "suite.lock"):
                with lock.open("rb") as handle:
                    try:
                        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        raise AssertionError("released lock with live worker")
            assert start_time(execution["pid"]) == execution["start_time"]
            os.kill(execution["pid"], signal.SIGKILL)
            until(
                lambda: json.loads((work / "execution.json").read_bytes())["ended_at"] is not None
            )
            assert all(not group_alive(g["pid"], g["start_time"]) for g in groups)
            assert f"{first}\tinterrupted, worker survived" in call([*cli, "report"])
            for lock in (claims / "suite.lock", board / "suite.lock"):
                with lock.open("rb") as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            # A failed assertion after killing the outer launcher must also reap
            # the disposable run before its server and checkout are torn down.
            if launcher.poll() is None:
                launcher.kill()
                launcher.wait(timeout=10)
            execution_file = work / "execution.json"
            if execution_file.is_file():
                record = json.loads(execution_file.read_bytes())
                pid = record["pid"]
                if pid and record.get("start_time") and start_time(pid) == record["start_time"]:
                    os.kill(pid, signal.SIGKILL)
                if pid:
                    until(lambda: json.loads(execution_file.read_bytes())["ended_at"] is not None)
            (control / "hold-worker").unlink(missing_ok=True)


def run(temp: Path, production: bool) -> None:
    control = temp / "control"
    control.mkdir()
    # Binding a listening socket proves exclusive ownership without probing a live service.
    with subprocess.Popen(
        [
            sys.executable,
            "-IB",
            str(ROOT / "tests/fake_ollama.py"),
            str(control),
        ],
        stdin=subprocess.DEVNULL,
    ) as fake:
        try:
            until(lambda: (control / "ready").exists() or fake.poll() is not None)
            if fake.poll() is not None or int((control / "ready").read_text()) != fake.pid:
                raise SystemExit(
                    "fake server could not bind loopback 11434; no study requests sent"
                )
            study = temp / "study"
            shutil.copytree(
                ROOT,
                study,
                ignore=shutil.ignore_patterns("prepared", "claims", "models.json", "__pycache__"),
            )
            shutil.copyfile(study / "models.example.json", study / "models.json")
            (study / ".offline").touch()
            claims = temp / "claims"
            env = os.environ | {
                "SIZE0_REHEARSAL_ROOT": str(study),
                "SIZE0_CLAIMS": str(claims),
                "SIZE0_DATE": "2000-01-01",
            }
            cli = ["sh", str(ROOT / "run-size0.sh")]

            def invoke(*args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
                if fake.poll() is not None:
                    raise RuntimeError("fake server exited")
                result = subprocess.run(
                    [*cli, *args, "--rehearsal"],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                )
                if (result.returncode == 0) != ok:
                    raise RuntimeError(str(args) + " " + result.stdout + result.stderr)
                return result

            invoke("prepare")
            order = schedule(True)
            for run_name in order:
                _, day, slot, condition = run_name.split("-")
                env["SIZE0_DATE"] = "2000-01-0" + day[1]
                if condition == "clean":
                    if run_name == order[0]:
                        (control / "malformed-next").touch()
                    invoke("preflight", slot)
                    if run_name == order[0]:
                        pin = json.loads(
                            next((claims / "preflights/rehearsal/q2").glob("*.json")).read_bytes()
                        )
                        assert (
                            pin["probes"][0]["parser_error"] and not pin["probes"][0]["native_call"]
                        )
                if run_name == order[1]:
                    (control / "drop-next").touch()
                    (control / "malformed-next").touch()
                invoke("rehearse", run_name)
                if run_name == order[1]:
                    p = json.loads((claims / run_name / "counts.json").read_bytes())["pooled"]
                    assert not (control / "malformed-next").exists()
                    work = claims / run_name
                    trials = rows(next(work.glob("store/*/trials.jsonl")))
                    (dropped,) = p["unexposed_trials"]
                    detail = p["unexposed_details"][dropped]
                    assert detail["reason"] == "transport_error"
                    assert detail["termination"] == next(
                        t["termination"] for t in trials if t["trial_id"] == dropped
                    )
                    # The other planted failure received a complete malformed tool call.
                    (malformed,) = [
                        t for t in trials if t["trial_id"] != dropped and t["outcome"] != "PASS"
                    ]
                    (receipt,) = [
                        r
                        for r in rows(work / "exchanges.jsonl")
                        if (r["seed"], r["arm"]) == (malformed["seed"], malformed["arm"])
                    ]
                    assert receipt["stream_completed"] and receipt["incomplete_reason"] is None
                    assert (
                        p["unexposed"] == 1
                        and len(p["unexposed_trials"]) == 1
                        and p["exposed"] == p["delivered"] - 1
                    )
            table = invoke("report").stdout
            assert all(f"{r}\tfinished" in table for r in order) and "partial" in table
            # A second disposable claims directory exercises a competing start and a killed CLI.
            claims = temp / "interrupted"
            env.update(SIZE0_CLAIMS=str(claims), SIZE0_DATE="2000-01-01")
            invoke("preflight", "q2")
            with subprocess.Popen(
                [*cli, "rehearse", order[0], "--rehearsal"], env=env, stdin=subprocess.DEVNULL
            ) as active:
                work = claims / order[0]
                until(lambda: active.poll() is not None or any(work.glob("store/*/manifest.json")))
                assert active.poll() is None
                refused = invoke("rehearse", order[1], ok=False)
                assert (
                    "temporarily unavailable" in refused.stderr.lower()
                    or "would block" in refused.stderr.lower()
                )
                process = json.loads((work / "execution.json").read_bytes())
                assert start_time(process["pid"]) == process["start_time"]
                os.kill(process["pid"], signal.SIGINT)
                assert active.wait(timeout=180) != 0
            assert json.loads((work / "execution.json").read_bytes())["exit_code"] != 0
            assert (work / "arci.log").is_file() and "permanent claim" in invoke(
                "rehearse", order[0], ok=False
            ).stderr
            assert f"{order[0]}\tinterrupted" in invoke("report").stdout
            if production:
                production_admission(temp, control)
        finally:
            (control / "hold-worker").unlink(missing_ok=True)
            fake.terminate()
    if production:
        print(
            "Native production rehearsal passed "
            "(pushed blobs, locks and surviving worker verified)."
        )
    else:
        print("Native rehearsal passed (two slots, two days, drop, competition and interruption).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="size0-native-") as tmp:
        run(Path(tmp).resolve(), args.production)
