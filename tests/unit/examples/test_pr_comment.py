"""Recorded GitHub API responses; no network and no message publication."""

from __future__ import annotations

import json
import runpy
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest
import yaml

Api = Callable[[str, str, dict[str, str] | None], object]
Post = Callable[[Mapping[str, str], Api], str]
POST = cast(Post, runpy.run_path(".github/scripts/pr_comment.py")["post_comment"])
MARKER = "<!-- arci-reliability-report:"
MARKER_FOR = cast(
    Callable[[Mapping[str, str]], str], runpy.run_path(".github/scripts/pr_comment.py")["marker"]
)


class FakeAPI:
    def __init__(self) -> None:
        self.comments: list[dict[str, object]] = json.loads(
            Path(__file__).with_name("pr_comments.json").read_text()
        )
        self.calls: list[tuple[str, str, dict[str, str] | None]] = []

    def __call__(self, method: str, endpoint: str, payload: dict[str, str] | None) -> object:
        self.calls.append((method, endpoint, payload))
        if method == "GET":
            return self.comments
        assert payload is not None
        if method == "POST":
            self.comments.append(
                {
                    "id": 41 + len(self.comments),
                    "user": {"login": "github-actions[bot]", "type": "Bot"},
                    "body": payload["body"],
                }
            )
        elif method == "PATCH":
            identifier = int(endpoint.rsplit("/", 1)[-1])
            next(c for c in self.comments if c["id"] == identifier)["body"] = payload["body"]
        else:
            raise AssertionError(method)
        return self.comments[-1]


def environment(tmp_path: Path) -> dict[str, str]:
    event, summary = tmp_path / "event.json", tmp_path / "summary.md"
    event.write_text('{"number": 7, "pull_request": {}}')
    summary.write_text("VERDICT: BLOCK (exit 1)\nbaseline: 20/20; candidate: 0/20\n")
    return {
        "GH_TOKEN": "fake-token",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_REPOSITORY": "owner/repo",
        "ARCI_SUMMARY": str(summary),
        "ARCI_VERDICT": "BLOCK",
        "ARCI_HEAD_SHA": "a" * 40,
        "GITHUB_RUN_ID": "3",
        "GITHUB_WORKFLOW": "Gate",
        "GITHUB_JOB": "experiment",
        "ARCI_MANIFEST": "arci.yaml",
        "ARCI_ARTIFACT_URL": "https://github.com/owner/repo/actions/runs/3/artifacts/9",
    }


def test_create_update_no_token_sequence(tmp_path: Path) -> None:
    api, env = FakeAPI(), environment(tmp_path)
    assert POST(env, api) == "ARCI comment created."
    assert len(api.comments) == 2  # Human marker spoof is never edited.
    body = str(api.comments[-1]["body"])
    assert body.startswith(MARKER) and "VERDICT: BLOCK" in body
    assert env["ARCI_ARTIFACT_URL"] in body
    Path(env["ARCI_SUMMARY"]).write_text("VERDICT: PASS (exit 0)\n")
    assert POST(env, api) == "ARCI comment updated."
    assert len(api.comments) == 2 and "VERDICT: PASS" in str(api.comments[-1]["body"])
    assert [c[0] for c in api.calls] == ["GET", "POST", "GET", "PATCH"]
    assert POST(env | {"GH_TOKEN": ""}, api) == "ARCI comment skipped: no token."
    assert len(api.calls) == 4


@pytest.mark.parametrize("kind", ["outside", "bad-event", "denied"])
def test_fail_soft(tmp_path: Path, kind: str) -> None:
    env = environment(tmp_path)
    api = FakeAPI()
    if kind == "outside":
        env["GITHUB_EVENT_NAME"] = "push"
    elif kind == "no-artifact":
        env["ARCI_ARTIFACT_URL"] = ""
    elif kind == "bad-url":
        env["ARCI_ARTIFACT_URL"] = "https://attacker.test/artifacts/9"
    elif kind == "bad-event":
        Path(env["GITHUB_EVENT_PATH"]).write_text("broken")

    def denied(method: str, endpoint: str, payload: dict[str, str] | None) -> object:
        raise subprocess.CalledProcessError(403, ["gh", method, endpoint, str(payload)])

    result = POST(env, denied if kind == "denied" else api)
    assert result.startswith("ARCI comment skipped:") and "\n" not in result
    assert not api.calls


def test_pagination_finds_existing_comment_before_create(tmp_path: Path) -> None:
    env, fake = environment(tmp_path), FakeAPI()
    POST(env, fake)
    calls: list[str] = []

    def paged(method: str, endpoint: str, payload: dict[str, str] | None) -> object:
        calls.append(endpoint)
        if method == "GET" and endpoint.endswith("page=1"):
            return [fake.comments[0]] * 100
        return fake(method, endpoint, payload)

    assert POST(env, paged) == "ARCI comment updated."
    assert calls[1].endswith("page=2") and len(fake.comments) == 2


def test_gh_uses_stdin_payload_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    gh = cast(Api, runpy.run_path(".github/scripts/pr_comment.py")["gh_api"])
    seen: list[dict[str, object]] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout='{"id":42}')

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gh("POST", "repos/owner/repo/issues/7/comments", {"body": "literal ` $()\n"}) == {
        "id": 42
    }
    assert seen[0]["timeout"] == 30 and seen[0]["check"] is True
    assert json.loads(str(seen[0]["input"])) == {"body": "literal ` $()\n"}


def test_action_keeps_gate_exit_and_comment_opt_in() -> None:
    action = yaml.safe_load(Path("action.yml").read_text())
    assert action["inputs"]["pr-comment"]["default"] == "false"
    assert "pull-requests: write" in action["inputs"]["pr-comment"]["description"]
    steps = action["runs"]["steps"]
    gate = next(s for s in steps if s.get("id") == "gate")
    assert "code=${PIPESTATUS[0]}" in gate["run"]
    assert 'exit "$code"' in gate["run"]
    assert "continue-on-error" not in gate
    for step in steps[3:]:
        assert "always()" in step["if"] and step["continue-on-error"] is True
    upload = next(s for s in steps if s.get("id") == "artifact")
    assert len(upload["uses"].split("@")[1]) == 40
    assert "inputs.pr-comment == 'true'" in steps[-1]["if"]


def test_prepare_report_uses_exact_run_and_keeps_stored_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.suite_report.test_reports import store_at

    store = store_at(tmp_path / "runs", "BLOCK")
    before = {p.name: p.read_bytes() for p in store.run_dir.iterdir()}
    stderr = tmp_path / "stderr"
    stderr.write_text(f"diagnostic\nrun store: {store.run_dir}\n")
    output = tmp_path / "report"
    gh_output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(gh_output))
    prepare = cast(
        Callable[[Path, Path], None], runpy.run_path(".github/scripts/prepare_report.py")["prepare"]
    )
    prepare(stderr, output)
    summary = (output / "summary.md").read_text()
    assert "VERDICT: BLOCK (exit 1)" in summary
    assert "baseline: 20/20" in summary and "candidate: 0/20" in summary
    assert "minus 20, zero 0, plus 0, errored 0 / tolerance 0" in summary
    assert "declared, never fired" in summary
    assert (output / "report.html").read_text().startswith("<!doctype html>")
    assert gh_output.read_text() == f"report_dir={output}\nartifact_name=report\n"
    assert {p.name: p.read_bytes() for p in store.run_dir.iterdir()} == before


@pytest.mark.parametrize(
    "failure", ["missing-summary", "missing-artifact", "bad-artifact", "malformed-url", "oversize"]
)
def test_current_run_replaces_stale_comment(tmp_path: Path, failure: str) -> None:
    env, api = environment(tmp_path), FakeAPI()
    Path(env["ARCI_SUMMARY"]).write_text("VERDICT: PASS (exit 0)\n")
    POST(env, api)
    env.update(ARCI_VERDICT="ERROR", ARCI_HEAD_SHA="b" * 40, GITHUB_RUN_ID="4")
    if failure == "missing-summary":
        Path(env["ARCI_SUMMARY"]).unlink()
    elif failure == "missing-artifact":
        env["ARCI_ARTIFACT_URL"] = ""
    elif failure == "malformed-url":
        env["ARCI_ARTIFACT_URL"] = "https://[broken"
    elif failure == "bad-artifact":
        env["ARCI_ARTIFACT_URL"] = "https://attacker.test/x"
    else:
        Path(env["ARCI_SUMMARY"]).write_text(
            "VERDICT: ERROR (exit 3)\n\nReason: invalid\n\n## Faults\n\n" + "| huge |\n" * 10000
        )
    assert POST(env, api) == "ARCI comment updated."
    body = str(api.comments[-1]["body"])
    assert "VERDICT: ERROR" in body and "VERDICT: PASS" not in body
    assert "b" * 40 in body and "run id: `4`" in body
    assert len(body.encode()) < 65000
    if failure == "oversize":
        assert "Summary truncated at a section boundary" in body
        assert "| huge |" not in body
    else:
        assert "Report unavailable" in body


def test_unknown_verdict_still_refreshes_marker(tmp_path: Path) -> None:
    env, api = environment(tmp_path), FakeAPI()
    POST(env, api)
    env.update(ARCI_VERDICT="", ARCI_ARTIFACT_URL="", GITHUB_RUN_ID="4")
    assert POST(env, api) == "ARCI comment updated."
    body = str(api.comments[-1]["body"])
    assert "Report unavailable" in body and "VERDICT:" not in body
    assert "a" * 40 in body and "run id: `4`" in body


@pytest.mark.parametrize(
    "key", ["ARCI_MANIFEST", "GITHUB_WORKFLOW", "GITHUB_JOB", "ARCI_COMMENT_ID"]
)
def test_experiment_markers_do_not_overwrite_each_other(tmp_path: Path, key: str) -> None:
    env, api = environment(tmp_path), FakeAPI()
    POST(env, api)
    old = str(api.comments[-1]["body"])
    env[key] = "second"
    Path(env["ARCI_SUMMARY"]).write_text("VERDICT: PASS (exit 0)\n")
    assert POST(env, api) == "ARCI comment created."
    assert len(api.comments) == 3
    assert api.comments[-2]["body"] == old
    assert "VERDICT: PASS" in str(api.comments[-1]["body"])
    assert MARKER_FOR(env | {"ARCI_COMMENT_ID": "stable", "ARCI_MANIFEST": "moved"}) == MARKER_FOR(
        env | {"ARCI_COMMENT_ID": "stable"}
    )


def test_racing_duplicates_are_refreshed_oldest_first_without_deletion(tmp_path: Path) -> None:
    env, api = environment(tmp_path), FakeAPI()
    POST(env, api)
    api.comments.insert(1, {**api.comments[-1], "id": 41})
    Path(env["ARCI_SUMMARY"]).write_text("VERDICT: ERROR (exit 3)\n")
    api.calls.clear()
    assert POST(env, api) == "ARCI comment updated."
    assert [call[0] for call in api.calls] == ["GET", "PATCH", "PATCH"]
    assert api.calls[1][1].endswith("/41") and api.calls[2][1].endswith("/42")
    assert len(api.comments) == 3
    assert all("VERDICT: ERROR" in str(c["body"]) for c in api.comments[1:])


def test_default_effective_steps_and_output_match_pre_p4() -> None:
    action = yaml.safe_load(Path("action.yml").read_text())
    before = yaml.safe_load(Path(__file__).with_name("action_before_p4.yml").read_text())
    effective = []
    for step in action["runs"]["steps"]:
        condition = step.get("if", "")
        if "inputs.pr-comment == 'true'" in condition:
            continue
        effective.append({key: value for key, value in step.items() if key != "if"})
    assert effective == before["runs"]["steps"]
    outputs = action["outputs"]
    assert (
        outputs["verdict"]["value"]
        == "${{ steps.gate.outputs.verdict || steps.comment_gate.outputs.verdict }}"
    )
    # The disabled comment gate has no outputs; the default verdict is the original gate output.
    outputs["verdict"]["value"] = outputs["verdict"]["value"].replace(
        " || steps.comment_gate.outputs.verdict", ""
    )
    assert outputs == before["outputs"]
    assert "concurrency group" in action["inputs"]["pr-comment"]["description"]
    assert "cancel-in-progress: false" in action["inputs"]["pr-comment"]["description"]


@pytest.mark.parametrize("suite", [False, True])
def test_structured_comment_excludes_failure_text_and_neutralizes_identifiers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suite: bool
) -> None:
    from arci.schema import Manifest, TrialEnvelope
    from arci.storage import ExperimentStore
    from arci.suite_schedule import create_suite_manifest
    from arci.suite_storage import SuiteStore
    from tests.acceptance.helpers import synthetic_trials
    from tests.acceptance.suite_helpers import round_trials
    from tests.unit.html_report.test_html_report import v1_evidence
    from tests.unit.suite_report.test_reports import evidence

    attack = '@octocat ![p](https://evil.test/p) <img src="https://evil.test/p"> [approve](https://evil.test)'
    label = "hostile`@octocat\r## fake"
    if suite:
        m, ts = evidence("BLOCK")
        m = create_suite_manifest(
            **(
                m.model_dump(exclude={"record_sha256", "experiment_id"})
                | {"baseline": m.baseline.model_copy(update={"label": label})}
            )
        )
        ts = round_trials(m, 1, [-1] * 20)
        store = SuiteStore(tmp_path / "runs", m)
    else:
        v1, ts = v1_evidence()
        v1 = Manifest.create(
            **(
                v1.model_dump(exclude={"record_sha256"})
                | {"baseline": v1.baseline.model_copy(update={"label": label})}
            )
        )
        ts = synthetic_trials(
            v1, condition_id="fetch_timeout", baseline_successes=12, candidate_successes=0
        )
        store = ExperimentStore(tmp_path / "runs", v1)
    for t in ts:
        store.append_trial(
            TrialEnvelope.create(
                **(t.model_dump(exclude={"record_sha256"}) | {"failure_detail": attack})
            )
        )
    stderr = tmp_path / "stderr"
    stderr.write_text(f"run store: {store.run_dir}\n")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    prepare = cast(
        Callable[[Path, Path], None], runpy.run_path(".github/scripts/prepare_report.py")["prepare"]
    )
    prepare(stderr, tmp_path / "report")
    body = (tmp_path / "report/summary.md").read_text()
    assert not any(s in body for s in ("![", "<img", "https:", "@octocat", "hostile`"))
    assert "`hostile[backtick]@\u200boctocat\\u000d## fake`" in body
    assert "Reason:" in body and "hard violations:" in body


def test_suite_hard_violation_comment_explains_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from arci.suite_storage import SuiteStore
    from tests.acceptance.suite_helpers import round_trials, suite_manifest

    m = suite_manifest()
    store = SuiteStore(tmp_path / "runs", m)
    for t in round_trials(m, 1, [0] * 20, hard=(3,)):
        store.append_trial(t)
    stderr = tmp_path / "stderr"
    stderr.write_text(f"run store: {store.run_dir}\n")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    prepare = cast(
        Callable[[Path, Path], None], runpy.run_path(".github/scripts/prepare_report.py")["prepare"]
    )
    prepare(stderr, tmp_path / "report")
    body = (tmp_path / "report/summary.md").read_text()
    assert "VERDICT: BLOCK" in body
    assert "Reason: `candidate hard violation`" in body
    assert "Candidate hard violations: 1." in body
    assert "this BLOCK is not a statistical finding" in body
