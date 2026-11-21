"""Offline controls, provenance, collection stops, CSV replay and historical ticket witnesses."""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import driver
from grade import HERE, Grade, Ticket, blob, export, git, install_hidden, reference_source, tickets
from grade import test_nodes as check_nodes
from run_trial import Executable, run_trial

ITEMS = tickets()
STANDIN = HERE / "tests/standin.py"


@pytest.fixture(autouse=True)
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("grade.ISOLATE_GRADER", os.environ.get("RUN5_CHECK_CONFINEMENT") == "1")
    monkeypatch.setenv("CODEX_BIN", str(STANDIN))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")


def script(tmp: Path, monkeypatch: pytest.MonkeyPatch, items: list[Ticket], mode: str) -> None:
    answers = {
        t["task"]: {
            p: base64.b64encode(reference_source(t, p)).decode() for p in t["allowed_paths"]
        }
        for t in items
    }
    path = tmp / "standin.json"
    path.write_text(json.dumps({"mode": mode, "answers": answers}))
    monkeypatch.setenv("STANDIN_SCRIPT", str(path))


@pytest.mark.parametrize("ticket", ITEMS, ids=[t["id"] for t in ITEMS])
def test_ticket(ticket: Ticket, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the held-out node(s) on both historical trees; do not count collection failures."""
    pre, fix = ticket["pre_fix_commit"], ticket["fix_commit"]
    assert git("rev-parse", fix + "^").decode().strip() == pre
    git("merge-base", "--is-ancestor", fix, "origin/main")
    for rev in (pre, fix, "v2.4.1", "HEAD"):
        pinned = {
            s.split("  ", 1)[1] for s in blob(rev, "FROZEN.sha256").decode().splitlines() if s
        }
        assert not pinned.intersection(ticket["allowed_paths"])
    f = ticket["hidden_test"]["path"]
    assert f in git("diff", "--name-only", pre, fix, "--", f).decode().splitlines()
    hidden = ticket["hidden_test"]["node_ids"]
    for rev in (pre, fix):
        tree = tmp_path / rev
        export(rev, tree)
        assert not (tree / ".git").exists()
        if rev == pre:
            parent = check_nodes(
                tree,
                ticket["visible_tests"],
                ticket["visible_cases"],
                tmp_path,
                tmp_path,
                "parent-visible",
            )
            assert parent[0] == "pass", parent
        install_hidden(tree, ticket)
        if preservation := ticket["hidden_test"].get("preservation"):
            kept = check_nodes(
                tree, preservation, len(preservation), tmp_path, tmp_path, rev + "-keep"
            )
            assert kept[0] == "pass", kept
        result = check_nodes(tree, hidden, len(hidden), tmp_path, tmp_path, rev)
        if rev == pre:
            assert result == ("fail", f"{rev}: pytest exit 1")
            log = (tmp_path / (rev + ".log")).read_text()
            assert all(f"FAILED {node}" in log for node in hidden)
        else:
            assert result[0] == "pass", result
    work, out = tmp_path / "private", tmp_path / "out"
    out.mkdir()
    script(tmp_path, monkeypatch, [ticket], "correct")
    accepted = run_trial(ticket, "baseline", 1, 1, work, out)
    assert accepted.outcome == "pass", accepted
    assert accepted.grade_seconds < 90
    print(f"REFERENCE {ticket['id']} {accepted.grade_seconds:.2f}s")
    script(tmp_path, monkeypatch, [ticket], "empty")
    rejected = run_trial(ticket, "candidate", 1, 2, work, out)
    assert rejected.grade_seconds < 90
    assert rejected.outcome == "fail" and "empty diff" in rejected.grader_evidence


@pytest.mark.parametrize(
    ("mode", "outcome", "reason"),
    [
        ("wrong", "fail", "pytest exit 1"),
        ("outside", "fail", "outside allowed"),
        ("test", "fail", "outside allowed"),
        ("ignored", "fail", "outside allowed"),
        ("sleep", "fail", "wall-clock limit"),
        ("quota", "error", "service marker quota"),
        ("crash", "fail", "agent crash"),
        ("unknown", "error", "unattributed"),
        ("auth", "error", "service marker auth"),
        ("rate", "error", "service marker rate"),
        ("transport", "error", "service marker transport"),
        ("server", "error", "service marker server"),
        ("retry", "error", "service marker retry"),
        ("service-stall", "error", "service marker transport"),
        ("unknown-stall", "error", "unattributed"),
        ("no-stream", "error", "unattributed"),
        ("missing", "error", "executable missing"),
        ("grader", "error", "grader failure"),
    ],
)
def test_classification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, outcome: str, reason: str
) -> None:
    ticket = ITEMS[0]
    script(tmp_path, monkeypatch, [ticket], "empty" if mode == "grader" else mode)
    if mode == "missing":
        monkeypatch.setenv("CODEX_BIN", str(tmp_path / "no-executable"))
    if mode == "grader":

        def broken(*args: object, **kwargs: object) -> Grade:
            raise RuntimeError("stand-in grader crash")

        monkeypatch.setattr("run_trial.grade", broken)
    row = run_trial(
        ticket,
        "candidate",
        1,
        1,
        tmp_path / "private",
        tmp_path,
        seconds=0.5 if mode in {"sleep", "service-stall", "unknown-stall"} else 10,
    )
    assert row.outcome == outcome and reason in row.grader_evidence, row
    if mode != "grader":
        patch = tmp_path / ("r01-" + ticket["id"] + "-candidate") / "change.patch"
        assert hashlib.sha256(patch.read_bytes()).hexdigest() == row.diff_sha256
    assert len(list((tmp_path / "private").glob("*.transcript"))) == (0 if mode == "missing" else 1)
    assert row.hit_time_limit == (mode in {"sleep", "service-stall", "unknown-stall"})
    assert row.audit.status == ("unauditable" if mode in {"missing", "no-stream"} else "clean")


def test_schedule() -> None:
    ids = [t["id"] for t in ITEMS]
    for r in range(1, 17):
        a = [driver.arm_order(ids, t, r) for t in ids]
        assert [p[0] for p in a].count("baseline") == 5
        assert all(set(p) == set(driver.ARMS) for p in a)
        assert a == [driver.arm_order(list(reversed(ids)), t, r) for t in ids]
    for t in ids:
        assert sum(driver.arm_order(ids, t, r)[0] == "baseline" for r in range(1, 17)) == 8


@pytest.mark.parametrize("outside_read", [False, True], ids=["clean", "outside-read"])
def test_two_complete_rounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outside_read: bool
) -> None:
    script(tmp_path, monkeypatch, ITEMS, "two-rounds")
    if outside_read:
        path = tmp_path / "standin.json"
        fixture = json.loads(path.read_bytes())
        fixture["events"] = [
            {"type": "item.completed", "item": {"type": "web_search", "id": "external"}}
        ]
        path.write_text(json.dumps(fixture))
    out = tmp_path / "out"
    out.mkdir()
    result = driver.campaign(ITEMS, tmp_path / "private", out, 4)
    assert result["status"] == "BLOCK" and result["complete_rounds"] == 2, result
    assert result["crossing_eligible_for_review"] is (not outside_read)
    assert result["audit"]["affected_pairs"] == (20 if outside_read else 0)
    assert result["trials"] == 40 and result["errored_pairs"] == 0
    assert json.loads((out / "round-01.json").read_bytes())["verdict"] == "INCONCLUSIVE"
    assert len(list((tmp_path / "private").glob("*.transcript"))) == 40
    assert not list(out.rglob("*.transcript"))
    ids = [t["id"] for t in ITEMS]
    records = [json.loads(line) for line in (out / "trials.jsonl").read_text().splitlines()]
    for r in (1, 2):
        for name in ids:
            pair = [t for t in records if t["round"] == r and t["ticket"] == name]
            assert [t["order"] for t in pair] == [1, 2]
            assert [t["arm"] for t in pair] == list(driver.arm_order(ids, name, r))
    for arm, expected in (("baseline", "pass"), ("candidate", "fail")):
        with (out / f"{arm}.csv").open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 20 and {row["outcome"] for row in rows} == {expected}


@pytest.mark.parametrize(
    ("mode", "reason", "count"),
    [
        ("quota", "three consecutive trial errors", 3),
        ("intermittent", "errored-pair tolerance exceeded", 5),
    ],
)
def test_midround_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str, count: int
) -> None:
    script(tmp_path, monkeypatch, ITEMS, mode)
    fixture = tmp_path / "standin.json"
    recipe = json.loads(fixture.read_bytes())
    recipe["events"] = [{"type": "item.completed", "item": {"type": "web_search", "id": "lookup"}}]
    fixture.write_text(json.dumps(recipe))
    if mode == "intermittent":
        ids = [t["id"] for t in ITEMS]
        path = tmp_path / "standin.json"
        data = json.loads(path.read_bytes())
        data["first_effort"] = {t["task"]: driver.arm_order(ids, t["id"], 1)[0] for t in ITEMS}
        path.write_text(json.dumps(data))
    out = tmp_path / "out"
    out.mkdir()
    result = driver.campaign(ITEMS, tmp_path / "private", out, 1)
    assert (result["reason"], result["status"], result["trials"]) == (reason, "ERROR", count)
    rows = [json.loads(line) for line in (out / "trials.jsonl").read_text().splitlines()]
    assert len(rows) == count
    assert sum(c["outside_read"] for c in result["audit"]["by_arm"].values()) == count
    assert result["audit"]["affected_pairs"] == len({r["ticket"] for r in rows})
    assert not result["audit"]["eligible"] and not result["crossing_eligible_for_review"]
    assert all(row["service_marker"] == "quota" for row in rows if row["outcome"] == "error")
    assert not (out / "baseline.csv").exists() and not (out / "round-01.json").exists()


def test_live_guard_refuses_draft_before_contact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(driver, "REGISTER", tmp_path / "missing")
    monkeypatch.setattr(driver, "MARKER", tmp_path / "marker")
    monkeypatch.setattr(driver, "OUTPUT", tmp_path / "out")
    with pytest.raises(ValueError, match="missing final registration"):
        driver.live(tmp_path / "work", 4)
    assert not (tmp_path / "marker").exists()


def test_start_guard_and_one_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Simulate published Git objects in memory. Every version call goes to the stand-in."""
    import shutil

    base = tmp_path / "checkout"
    folder = base / "codex-effort"
    folder.mkdir(parents=True)
    (folder / "rule.yaml").write_text("rule bytes\n")
    manifest = folder / "digests.sha256"
    manifest.write_text(
        hashlib.sha256((folder / "rule.yaml").read_bytes()).hexdigest()
        + "  codex-effort/rule.yaml\n"
    )
    registration = base / "PREREGISTRATION-codex-effort.md"
    registration.write_text(hashlib.sha256(manifest.read_bytes()).hexdigest())
    objects = {
        str(p.relative_to(base)): p.read_bytes()
        for p in (manifest, registration, folder / "rule.yaml")
    }
    tip = "b" * 40

    def read_git(*args: str) -> bytes:
        if args[0] == "rev-parse":
            return tip.encode()
        assert args[:2] == ("ls-tree", tip)
        return b"100644 blob"

    def read_blob(commit: str, name: str) -> bytes:
        assert commit == tip
        return objects[name]

    monkeypatch.setattr(driver, "git", read_git)
    monkeypatch.setattr(driver, "blob", read_blob)
    monkeypatch.setattr(driver, "published_tip", lambda: tip)
    monkeypatch.setattr(driver, "PRIVATE_WORK", tmp_path / "work")
    monkeypatch.setattr(driver, "SHARED_MARKER", tmp_path / "shared-start")
    monkeypatch.setattr(driver, "HERE", folder)
    monkeypatch.setattr(driver, "REPO", base)
    monkeypatch.setattr(driver, "REGISTER", registration)
    monkeypatch.setattr(driver, "DIGESTS", manifest)
    monkeypatch.setattr(driver, "MARKER", folder / "codex-effort.started")
    monkeypatch.setattr(driver, "OUTPUT", folder / "runs-codex-effort")
    with pytest.raises(ValueError, match="HEAD differs"):
        driver.check_registration("c" * 40)
    (folder / "rule.yaml").write_text("changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        driver.check_registration(tip)
    (folder / "rule.yaml").write_bytes(objects["codex-effort/rule.yaml"])
    registration.write_text("changed")
    with pytest.raises(ValueError, match="published bytes differ"):
        driver.check_registration(tip)
    registration.write_bytes(objects[registration.name])
    manifest.write_text("")
    with pytest.raises(ValueError, match="incomplete"):
        driver.check_registration(tip)
    manifest.write_bytes(objects["codex-effort/digests.sha256"])

    def fixture_checks(work: Path) -> bytes:
        assert work.is_dir()
        return b"fixture check"

    monkeypatch.setattr(driver, "standin_checks", fixture_checks)
    # Satisfy the production interpreter guard even for pytest launched from another shim.
    assert shutil.which(str(STANDIN)) is not None

    def fixture_campaign(*args: object, executable: Executable) -> dict[str, str]:
        assert len(args) == 4
        script(tmp_path, monkeypatch, ITEMS[:1], "empty")
        row = run_trial(
            ITEMS[0],
            "baseline",
            1,
            1,
            tmp_path / "work",
            driver.OUTPUT,
            expected_executable=executable,
        )
        saved = json.loads((driver.OUTPUT / "start.json").read_bytes())
        assert (
            row.executable_sha256
            == saved["executable_sha256"]
            == hashlib.sha256(STANDIN.read_bytes()).hexdigest()
        )
        assert (
            row.native_executable_sha256
            == saved["native_executable_sha256"]
            == hashlib.sha256(Path(saved["native"]).read_bytes()).hexdigest()
        )
        assert row.executable_sha256 != row.native_executable_sha256
        return {"status": "INCONCLUSIVE"}

    monkeypatch.setattr(driver, "campaign", fixture_campaign)
    driver.live(tmp_path / "work", 4, check_only=True)
    assert "Start check passed" in capsys.readouterr().out and not driver.SHARED_MARKER.exists()
    with pytest.raises(SystemExit) as caught:
        driver.live(tmp_path / "work", 4)
    assert caught.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INCONCLUSIVE"
    assert json.loads((driver.OUTPUT / "start.json").read_bytes())["codex"] == "standin 1"
    assert driver.SHARED_MARKER.is_dir()
    # A different checkout has neither local marker nor local output.
    monkeypatch.setattr(driver, "MARKER", tmp_path / "another-checkout-marker")
    monkeypatch.setattr(driver, "OUTPUT", tmp_path / "another-output")
    with pytest.raises(ValueError, match="prior start"):
        driver.live(tmp_path / "another", 4)
