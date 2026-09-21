"""Portable failure bundle creation and offline replay."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path, PurePosixPath

from arci.hashing import hash_bytes
from arci.runner import run_trial
from arci.schema import (
    Manifest,
    Outcome,
    ReplayBundle,
    ReplayResult,
    ReplayStatus,
    Termination,
    ToolMode,
    TrialEnvelope,
    TrialSpec,
)


def _relative_path(path: str) -> PurePosixPath:
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"include path must be relative: {path}")
    return relative


def make_bundle(
    manifest: Manifest,
    trial: TrialEnvelope,
    spec: TrialSpec,
    *,
    root: Path | str | None = None,
    include: tuple[str, ...] = (),
) -> ReplayBundle:
    if trial.outcome is Outcome.PASS:
        raise ValueError("a passing trial cannot be bundled as a reproducer")
    if trial.failure_fingerprint is None:
        raise ValueError("failing trial has no failure fingerprint")
    if include and root is None:
        raise ValueError("root is required when include paths are supplied")

    files: dict[str, str] = {}
    fixtures: dict[str, str] = {}
    root_path = None if root is None else Path(root)
    for item in include:
        relative = _relative_path(item)
        assert root_path is not None
        data = (root_path / Path(*relative.parts)).read_bytes()
        key = relative.as_posix()
        files[key] = base64.b64encode(data).decode("ascii")
        fixtures[key] = hash_bytes(data)

    lock_sha256 = None
    if root_path is not None and (root_path / "uv.lock").is_file():
        lock_sha256 = hash_bytes((root_path / "uv.lock").read_bytes())
    replay_spec = spec.model_copy(
        update={
            "tool_mode": ToolMode.REPLAY,
            "recording": trial.recording,
            "replay_final_state": trial.final_state,
        }
    )
    return ReplayBundle.create(
        manifest=manifest,
        spec=replay_spec,
        expected_outcome=trial.outcome,
        expected_fingerprint=trial.failure_fingerprint,
        source_trial_sha256=trial.record_sha256,
        files=files,
        fixtures=fixtures,
        lock_sha256=lock_sha256,
    )


def replay(bundle: ReplayBundle) -> ReplayResult:
    """Replay a bundle without allowing malformed input to escape as an exception."""
    try:
        if not bundle.validate_seal():
            return ReplayResult(status=ReplayStatus.INVALID, detail="bundle seal is invalid")
        if set(bundle.files) != set(bundle.fixtures):
            return ReplayResult(status=ReplayStatus.INVALID, detail="fixture inventory mismatch")

        relative_paths = {name: _relative_path(name) for name in {*bundle.files, *bundle.fixtures}}
        decoded: dict[str, bytes] = {}
        for name, payload in bundle.files.items():
            data = base64.b64decode(payload, validate=True)
            if hash_bytes(data) != bundle.fixtures[name]:
                return ReplayResult(status=ReplayStatus.INVALID, detail="fixture hash mismatch")
            decoded[relative_paths[name].as_posix()] = data

        with tempfile.TemporaryDirectory(prefix="arci-replay-") as directory:
            root = Path(directory)
            for name, data in decoded.items():
                destination = root / Path(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            observed = run_trial(
                bundle.spec,
                lambda _event: None,
                bundle.manifest.contract,
                extra_pythonpath=(directory,),
            )

        if observed.termination is Termination.REPLAY_MISS:
            return ReplayResult(
                status=ReplayStatus.INVALID,
                observed_outcome=observed.outcome,
                observed_fingerprint=observed.failure_fingerprint,
                detail="recording mismatch",
            )
        reproduced = (
            observed.outcome is bundle.expected_outcome
            and observed.failure_fingerprint == bundle.expected_fingerprint
        )
        return ReplayResult(
            status=ReplayStatus.REPRODUCED if reproduced else ReplayStatus.NOT_REPRODUCED,
            observed_outcome=observed.outcome,
            observed_fingerprint=observed.failure_fingerprint,
            detail="failure reproduced" if reproduced else "observed result differs",
        )
    except Exception as exc:
        return ReplayResult(
            status=ReplayStatus.INVALID,
            detail=f"{type(exc).__name__}: {exc}".splitlines()[0],
        )
