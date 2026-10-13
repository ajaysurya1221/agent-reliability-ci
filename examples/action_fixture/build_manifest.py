"""Regenerate ``manifest.json``: the packaged demo's A-vs-B experiment, 200 trials per arm.

    python examples/action_fixture/build_manifest.py

Deterministic: ``created_at`` stays empty, as the builder leaves it, so a regeneration is
byte-identical to the committed file (checked by ``tests/unit/examples/test_action_fixture.py``).
"""

from __future__ import annotations

from pathlib import Path

from arci.demo.experiment import build_manifest

MANIFEST = Path(__file__).resolve().parent / "manifest.json"
N_PER_ARM = 200
CANDIDATE = "agent_b"


def render() -> str:
    """The fixture's exact bytes, as text."""
    return build_manifest(n_per_arm=N_PER_ARM, candidate=CANDIDATE).model_dump_json(indent=2) + "\n"


def write(path: Path = MANIFEST) -> Path:
    path.write_text(render(), encoding="utf-8")
    return path


def main() -> int:
    print(f"wrote {write()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
