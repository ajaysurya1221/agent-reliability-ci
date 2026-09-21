"""Append-only experiment storage owned by the parent process."""

from __future__ import annotations

from pathlib import Path

from arci.schema import Event, Manifest, TrialEnvelope


class ExperimentStore:
    def __init__(self, out_dir: Path | str, manifest: Manifest) -> None:
        self.run_dir = Path(out_dir) / manifest.experiment_id
        if self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise FileExistsError(f"run directory is not empty: {self.run_dir}")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2) + "\n")

    def append_event(self, event: Event) -> None:
        with (self.run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(event.model_dump_json() + "\n")

    def append_trial(self, trial: TrialEnvelope) -> None:
        with (self.run_dir / "trials.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(trial.model_dump_json() + "\n")


def load_run(run_dir: Path | str) -> tuple[Manifest, tuple[TrialEnvelope, ...]]:
    directory = Path(run_dir)
    manifest = Manifest.model_validate_json((directory / "manifest.json").read_text())
    if not manifest.validate_seal():
        raise ValueError("manifest seal is invalid")
    path = directory / "trials.jsonl"
    trials = tuple(
        TrialEnvelope.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    )
    if any(not trial.validate_seal() for trial in trials):
        raise ValueError("trial seal is invalid")
    return manifest, trials
