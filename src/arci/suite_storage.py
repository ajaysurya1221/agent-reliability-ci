"""Parent-owned suite stores with the ordinary trial/event JSONL layout."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path

from arci.hashing import canonical_json
from arci.schema import SCHEMA_VERSION, Event, TrialEnvelope
from arci.suite_schedule import suite_experiment_id
from arci.suite_schema import SUITE_SCHEMA_VERSION, SuiteDecision, SuiteManifest
from arci.suite_stats import check_suite_plan


def manifest_schema_version(path: Path | str) -> str:
    """Read the explicit version of a manifest file or run directory, never infer it."""
    source = Path(path)
    if source.is_dir():
        source /= "manifest.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest must be an object with schema_version")
    version = data.get("schema_version")
    if version not in (SCHEMA_VERSION, SUITE_SCHEMA_VERSION):
        raise ValueError("manifest schema_version must be arci/0.5 or arci-suite/1")
    return str(version)


def validate_suite_manifest(manifest: SuiteManifest) -> SuiteManifest:
    """Rebuild copies as well as checking seals before using an id as a path."""
    rebuilt = SuiteManifest.model_validate(manifest.model_dump(mode="python", warnings=False))
    canonical_json(rebuilt.model_dump(mode="json"))
    if not rebuilt.validate_seal():
        raise ValueError("suite manifest seal is invalid")
    if rebuilt.experiment_id != suite_experiment_id(rebuilt):
        raise ValueError("suite experiment_id does not match the rule digest")
    check_suite_plan(rebuilt)
    return rebuilt


class SuiteStore:
    def __init__(self, out_dir: Path | str, manifest: SuiteManifest) -> None:
        manifest = validate_suite_manifest(manifest)
        self.run_dir = Path(out_dir) / manifest.experiment_id
        # Exclusive creation also refuses empty existing directories and symlinks.
        self.run_dir.mkdir(parents=True, exist_ok=False)
        (self.run_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (self.run_dir / "trials.jsonl").touch(exist_ok=False)
        (self.run_dir / "events.jsonl").touch(exist_ok=False)
        self._round_offsets: dict[int, dict[str, int]] = {}

    def write_round(
        self, round_number: int, trials: Sequence[TrialEnvelope], events: Sequence[Event]
    ) -> None:
        """Publish whole JSONL files atomically; retrying this round is idempotent.

        Prefix offsets keep a handled interruption between the two replacements from
        duplicating lines. Existing round bytes are preserved. This is not a two-file
        transaction or protection against SIGKILL or disk failure.
        """
        offsets = self._round_offsets.setdefault(
            round_number,
            {
                name: (self.run_dir / name).stat().st_size
                for name in ("events.jsonl", "trials.jsonl")
            },
        )
        for name, records in (("events.jsonl", events), ("trials.jsonl", trials)):
            path = self.run_dir / name
            content = path.read_bytes()[: offsets[name]] + "".join(
                record.model_dump_json() + "\n" for record in records
            ).encode("utf-8")
            temporary = path.with_suffix(".tmp")
            try:
                temporary.write_bytes(content)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)

    def append_event(self, event: Event) -> None:
        with (self.run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")

    def append_trial(self, trial: TrialEnvelope) -> None:
        with (self.run_dir / "trials.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(trial.model_dump_json() + "\n")

    def write_decision(self, decision: SuiteDecision) -> None:
        if not decision.validate_seal():
            raise ValueError("suite decision seal is invalid")
        (self.run_dir / "decision.json").write_text(
            decision.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )


def load_suite_run(run_dir: Path | str) -> tuple[SuiteManifest, tuple[TrialEnvelope, ...]]:
    directory = Path(run_dir)
    manifest = validate_suite_manifest(
        SuiteManifest.model_validate_json((directory / "manifest.json").read_text(encoding="utf-8"))
    )
    trials = tuple(
        TrialEnvelope.model_validate_json(line)
        for line in (directory / "trials.jsonl").read_text(encoding="utf-8").split("\n")
        if line.strip()
    )
    if any(not trial.validate_seal() for trial in trials):
        raise ValueError("trial seal is invalid")
    return manifest, trials
