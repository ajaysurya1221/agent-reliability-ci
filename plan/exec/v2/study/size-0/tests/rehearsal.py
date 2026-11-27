"""Exercise two slots on two simulated dates in a disposable copy."""

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from descriptors import RUNS, Row, encoded, models, read  # noqa: E402
from identity import inspect_model  # noqa: E402
from launcher import run_suite  # noqa: E402


def rehearse(root: Path) -> None:
    shutil.copytree(
        ROOT,
        root,
        ignore=shutil.ignore_patterns(
            "claims",
            "prepared",
            "__pycache__",
            ".ruff_cache",
            ".pytest_cache",
            "_offline",
            "models.json",
        ),
    )
    (root / ".offline").touch()
    shutil.copyfile(root / "models.example.json", root / "models.json")
    os.environ["SIZE0_CLAIMS"] = str(root / "claims")
    (root / "claims").mkdir()
    for slot, model in models(root).items():
        probe: Row = dict(
            native_call=True,
            parser_error=False,
            token_repeated=True,
            thinking=False,
            seconds=0,
            load_seconds=0,
            identity=inspect_model(root, model, True),
        )
        history = root / "claims/preflights/rehearsal" / slot
        history.mkdir(parents=True)
        (history / "00000001-fixture.json").write_bytes(
            encoded(
                dict(
                    slot=slot,
                    cold=True,
                    status="qualified",
                    model=model,
                    mode="rehearsal",
                    registration="rehearsal",
                    probes=[probe] * 5,
                    before=probe["identity"] | dict(loaded_digest=None, loaded_context=None),
                    cold_load_seconds=0,
                )
            )
        )
    cli = [sys.executable, "-EsB", str(root / "launcher.py")]
    subprocess.run([*cli, "prepare"], stdin=subprocess.DEVNULL, check=True)
    for run in RUNS:
        if run.split("-")[2] in ("q2", "q4"):
            run_suite(root, run, rehearsal_day=date(2000, 1, int(run.split("-")[1][1])))
            pooled = read(root / "claims" / run / "counts.json")["pooled"]
            assert pooled["trials"] == pooled["passed"] == 160
            assert (
                pooled["read_again"] == pooled["delivered"] == (160 if run.endswith("-null") else 0)
            )
    subprocess.run([*cli, "report", "--rehearsal"], stdin=subprocess.DEVNULL, check=True)
    command = [os.environ["SIZE0_REPO_PYTHON"], "-B", str(ROOT / "check_evidence.py")]
    subprocess.run([*command, str(root), "--rehearsal"], check=True, stdin=subprocess.DEVNULL)
    for damage in ("events", "descriptor"):
        copy = root.parent / damage
        shutil.copytree(root, copy)
        if damage == "events":
            import json

            path = next((copy / "claims" / RUNS[0]).glob("store/*/trials.jsonl"))
            lines = path.read_text().splitlines()
            trial = json.loads(lines[0])
            trial["events"][1]["payload"]["arguments"]["sku"] = "changed"
            lines[0] = json.dumps(trial)
            path.write_text("\n".join(lines) + "\n")
        else:
            path = copy / "prepared" / (RUNS[0] + ".yaml")
            path.write_bytes(path.read_bytes() + b"\n")
        child = subprocess.run(
            [*command, str(copy), "--claims", str(copy / "claims"), "--rehearsal"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        expected = "finished inventory differs" if damage == "events" else "descriptor differs"
        assert child.returncode != 0 and expected in child.stderr, (
            damage,
            child.stdout,
            child.stderr,
        )
        print(f"Rejected changed {damage}")
    print("Offline rehearsal passed (8 runs, 1280 trials).")


if __name__ == "__main__":
    with TemporaryDirectory(prefix="size0-offline-") as temp:
        rehearse(Path(temp).resolve() / "study")
