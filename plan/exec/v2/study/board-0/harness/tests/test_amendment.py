"""Amendment 1 eligibility, one-shot claims, descriptor preservation and evidence."""

import io
import json
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import admission
import check_evidence
import inputs
import launcher
import publication
from common import NOTE, ROOT, Row, models, pin_name, read, registry, schedule, write
from worlds import rows


@pytest.fixture
def study(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copyfile(ROOT / "models.json", tmp_path / "models.json")
    claims = tmp_path / "claims"
    claims.mkdir()
    monkeypatch.setattr(admission, "CLAIMS", claims)
    for module in (admission, inputs, launcher, publication):
        monkeypatch.setattr(module, "ROOT", tmp_path)

    def digests(names: list[str]) -> str:
        return inputs.digests(names, tmp_path)

    monkeypatch.setattr(admission, "digests", digests)
    return tmp_path


def finish(study: Path, model: Row, passed: bool) -> None:
    run = model["pin"]
    record = {"run": run, "ok": passed, "model": model}
    write(study / "pins" / (run + ".json"), record)
    directory = study / "claims" / run
    write(directory / "claim.json", {"model": model, "registration": "a" * 40})
    write(
        directory / "finished.json", record | {"files": inputs.digests(inputs.outputs(run), study)}
    )


def test_old_names_and_spare_admission(study: Path) -> None:
    config = registry(study / "models.json")
    slots = config["slots"]
    claims = study / "claims"
    old = "board0-pin-M1"
    assert old not in schedule(slots)
    with pytest.raises(ValueError, match="unknown RUN"):
        launcher.execute(old, slots)
    with pytest.raises(ValueError, match="unfinished pin"):
        launcher.roster()
    for model in slots[:-1]:
        finish(study, model, False)
    with pytest.raises(ValueError, match="unfinished pin"):
        admission.order_guard(pin_name("S1"), slots, claims, date.today())
    finish(study, slots[-1], True)
    for spare in config["spares"]:
        admission.order_guard(spare["pin"], slots, claims, date.today())
        finish(study, spare, True)
        with pytest.raises(ValueError, match="already claimed"):
            admission.order_guard(spare["pin"], slots, claims, date.today())
    assert not (claims / old).exists()


@pytest.mark.parametrize(
    ("failed", "spare_results", "pins"),
    [
        ([], [], ["M1", "M2", "M3", "M4", "M5"]),
        (["M4"], [True], ["M1", "M2", "M3", "S1", "M5"]),
        (["M2", "M5"], [True, True], ["M1", "S1", "M3", "M4", "S2"]),
        (["M1", "M3", "M5"], [True, True], ["S1", "M2", "S2", "M4", None]),
        (["M2", "M3"], [False, True], ["M1", None, "S2", "M4", "M5"]),
    ],
)
def test_final_roster(
    study: Path, failed: list[str], spare_results: list[bool], pins: list[str | None]
) -> None:
    path = study / "models.json"
    config = registry(path)
    claims = study / "claims"
    for m in config["slots"]:
        finish(study, m, m["slot"] not in failed)
    for i, spare in enumerate(config["spares"]):
        if i < len(spare_results):
            with pytest.raises(ValueError, match="unfinished pin"):
                launcher.roster()
            finish(study, spare, spare_results[i])
        else:
            with pytest.raises(ValueError, match="not required"):
                admission.order_guard(spare["pin"], config["slots"], claims, date.today())
    final = launcher.roster()
    snapshot = path.read_bytes()
    assert launcher.roster() == models(path) == final and path.read_bytes() == snapshot
    for name, actual, original in zip(pins, final, config["slots"], strict=True):
        source = next((s for s in config["spares"] if s["slot"] == name), original)
        expected = source | {"slot": original["slot"]}
        if name is None:
            expected["vacant"] = True
        assert actual == expected


def test_vacant_order_and_report(study: Path) -> None:
    config = registry(study / "models.json")
    for m in config["slots"]:
        finish(study, m, m["slot"] in {"M2", "M3", "M4"})
    for spare in config["spares"]:
        finish(study, spare, False)
    slots = launcher.roster()
    claims = study / "claims"
    today = date(2002, 1, 2)
    for run in schedule(slots):
        if "-pin2-" in run:
            continue
        if run.split("-")[2] in ("M1", "M5"):
            with pytest.raises(ValueError, match="vacant slot"):
                admission.order_guard(run, slots, claims, today)
        else:
            admission.order_guard(run, slots, claims, today)
            write(claims / run / "finished.json", {"ok": True})
            write(claims / run / "claim.json", {"date": "2002-01-01"})
    result = publication.report(slots)
    assert result.count("vacant: pin failed. Model-day undecided.") == 4
    members = inputs.inventory(slots)
    check_evidence.check_inventory(members, slots, rows())
    assert len([n for n in members if n.startswith("runs/") and n.endswith("decision.json")]) == 6
    assert "runs/board0-d2-M5-E/descriptor.yaml" in members
    for name in ["pins/board0-pin-M1.json", "pins/board0-pin2-M3.json", "pins/board0-pin2-S2.json"]:
        with pytest.raises(ValueError, match="inventory"):
            check_evidence.check_inventory([n for n in members if n != name], slots, rows())


@pytest.mark.parametrize("field", ["tag", "digest", "pin"])
def test_substituted_pin_binding(study: Path, field: str) -> None:
    config = registry(study / "models.json")
    for m in config["slots"]:
        finish(study, m, m["slot"] != "M1")
    finish(study, config["spares"][0], True)
    slots = launcher.roster()
    run = "board0-d1-M1-clean"
    admission.order_guard(run, slots, study / "claims", date.today())
    slots[0][field] = config["slots"][0][field]
    with pytest.raises(ValueError, match="roster differs"):
        admission.order_guard(run, slots, study / "claims", date.today())


def test_only_substitute_descriptors_change(study: Path) -> None:
    config = registry(study / "models.json")
    for m in config["slots"]:
        finish(study, m, m["slot"] not in {"M2", "M3"})
    for spare in config["spares"]:
        finish(study, spare, spare["slot"] == "S1")
    slots = launcher.roster()
    names = inputs.descriptors(slots)
    for n in [*names, NOTE]:
        path = study / n
        path.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(ROOT / n, path)
    original = {n: (study / n).read_bytes() for n in names}
    stamps = {n: (study / n).stat().st_mtime_ns for n in names}
    doc = read(ROOT / "tasks/tasks.json")
    bad = study / names[-1]
    bad.write_bytes(bad.read_bytes() + b" ")
    with pytest.raises(ValueError, match="descriptor"):
        launcher.prepare_descriptors(slots, doc, offline=False)
    assert all((study / n).read_bytes() == original[n] for n in names[:-1])
    bad.write_bytes(original[names[-1]])
    launcher.prepare_descriptors(slots, doc, offline=False)
    for n in names:
        if "-M2-" in n:
            assert (study / n).read_bytes() == original[n].replace(
                config["slots"][1]["tag"].encode(), slots[1]["tag"].encode()
            )
        else:
            assert (study / n).read_bytes() == original[n]
            if n != names[-1]:
                assert (study / n).stat().st_mtime_ns == stamps[n]
    assert (study / NOTE).read_bytes() == (ROOT / NOTE).read_bytes()
    launcher.prepare_descriptors(slots, doc, offline=False)
    (study / NOTE).write_text(inputs.digests(names, study))
    launcher.prepare_descriptors(slots, doc, offline=False)


def test_pin_registration_transition(study: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slot = models(study / "models.json")[0]
    finish(study, slot, True)
    run = slot["pin"]
    first, second = "a" * 40, "b" * 40
    ancestor = first

    def merge_base(*args: str) -> bytes:
        assert args == ("merge-base", first, second)
        return ancestor.encode()

    monkeypatch.setattr(admission, "git", merge_base)
    with pytest.raises(ValueError, match="amendment 2"):
        admission.finished(run, study / "claims", first, board=True)
    admission.finished(run, study / "claims", second, board=True)
    ancestor = "unrelated"
    with pytest.raises(ValueError, match="amendment 2"):
        admission.finished(run, study / "claims", second, board=True)


def test_historical_pins_only_check_name() -> None:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        for i in range(1, 6):
            name = f"board0-pin-M{i}"
            z.writestr(f"pins/{name}.json", json.dumps({"run": name if i < 5 else "wrong"}))
        with pytest.raises(ValueError, match="historical pin board0-pin-M5"):
            check_evidence.verify_pins(z, {"slots": [], "spares": []}, False)


def test_five_vacancies_verify_zero_suites(study: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import nullcontext

    import pin
    from agent import Capture
    from common import LIST, dump, sha
    from fake_ollama import FakeOllama

    config = registry(study / "models.json")
    server = FakeOllama()

    def dispatch(
        run: str, model: Row, endpoint: str, body: bytes | None, capture: Capture | None = None
    ) -> tuple[int, bytes]:
        if capture and body:
            capture(body)
        return server.handle("POST" if body else "GET", "/api/" + endpoint, body or b"")

    def no_sampling(enabled: bool) -> nullcontext[list[int]]:
        return nullcontext([])

    monkeypatch.setattr(pin, "request", dispatch)
    monkeypatch.setattr(pin, "memory_sample", no_sampling)
    for model in config["slots"] + config["spares"]:
        run = model["pin"]
        server.echo_tag = model["tag"]
        with pytest.raises(pin.PinFailed):
            pin.execute(run, model, study / "pins" / (run + ".json"), offline=False)
    slots = [m | {"vacant": True} for m in config["slots"]]
    (study / "models.json").write_bytes(dump(config | {"slots": slots}))
    for i in range(1, 6):
        run = f"board0-pin-M{i}"
        write(study / "pins" / (run + ".json"), {"run": run})
    for name in inputs.sources():
        if name != "models.json":
            dest = study / name
            dest.parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(ROOT / name, dest)
    # Vacancies keep every frozen descriptor even when no suite can run.
    launcher.prepare_descriptors(config["slots"], read(study / "tasks/tasks.json"), offline=False)
    (study / NOTE).write_text(inputs.digests(inputs.descriptors(slots), study))
    (study / LIST).write_text(inputs.digests(inputs.sources(), study))
    (study / "result.md").write_text(publication.report(slots, offline=False))
    path = study / "vacant.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name in inputs.inventory(slots):
            z.write(study / name, name)
    side = study / "vacant.sha256"
    side.write_text(sha(path.read_bytes()))
    assert check_evidence.verify(path, side, rehearsal=False) == 0
