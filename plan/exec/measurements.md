# Measurements log (orchestrator-recorded; receipts proper go to docs/measurement/receipts once T10 lands)

| when (UTC) | what | machine | result |
|---|---|---|---|
| 2026-10-13 03:36 | `examples/retry_agent/hero_demo.py --n 200` from the checkout, 8 workers | 15-core Apple Silicon Mac, Python 3.13.12 | 38.2 s wall, exit 0 |
| 2026-10-13 04:05 | T02 wheel smoke: `uv build --no-sources` from `sprint/demo` (2ae4bfd), then from an EMPTY directory `uvx --from <wheel> arci demo` (uvx env creation included) | same | 1:12.25 wall, exit 0, "All six steps held", A 192/200 B 132/200, 0 files left in cwd; wheel 115 KB (38 files, incl. arci/demo/* and arci/__main__.py); sdist 5.9 MB (unrestricted until T12) |

## Cold read of the README (AI-agent labelled; not a cold reader under protocol 1.4)

- When: 2026-10-13T07:08Z. Reader: Claude Opus 5.5 (effort high) general-purpose subagent with no
  project context, allowed to read only `README.md` at main `6f52431` (the first screen is the one
  that ships in v0.8.0; T12 changes only the pins below the fold). Scorer: Fable (orchestrator), key
  in `docs/measurement/ttfv-protocol.md` §5. Raw answers and per-question notes:
  `plan/exec/cold-read-2026-10-13.json`.
- Result: q1–q5 all correct (5/5); the BLOCK interpretation also correct. The reader read past the
  first screen (`read_whole_readme: true`; its own reading-time estimate 7 min). Memo target for
  cold readers: ≥ 80 % answer all five; this single AI-agent run is a check of the text, not a
  measurement of cold readers (none recruited in this run; HUMAN_INBOX 5).

## Own-agent TTFV, Track B (maintainer-machine run by the orchestrator; AI-agent labelled)

- 2026-10-13T07:31:44Z–07:31:47Z, sample tree `examples/recipes/python_agent` copied outside the
  checkout, local 0.8.0 wheel (sha256 10ddc682…2899, built from main 48e60ac), warm uv cache.
  install 0 s (uv venv + uv pip install; the `uv tool install` route is denied here), scaffold 1 s,
  run 2 s, store validated (gate reproduces the line; decision sha unchanged), total 3 s to a
  validated INCONCLUSIVE at N=8; agent execution summed over 16 trials 5.9 s. Receipt:
  `docs/measurement/receipts/2026-10-13-claude-fable-orchestrator-own-agent.json`. This measures the
  tool path, not a person reading the README or writing references; the memo's ≤ 10 min target is
  for cold users, none measured in this run.

## Packaged demo TTFV, Track A (maintainer-machine runs by the orchestrator; AI-agent labelled; local 0.8.0 wheel)

- `uvx --from <wheel> arci demo` from an empty directory, default workers, wheel sha256 10ddc682…2899
  (built from main 48e60ac; PyPI not yet published at measurement time). Three samples:
  cold uv cache (fresh UV_CACHE_DIR): install 9 s, run 71 s, total 80 s; warm cache: 1 s + 71 s = 72 s;
  warm cache: 1 s + 72 s = 73 s. All exit 0, "All six steps held". Receipt (the cold run):
  `docs/measurement/receipts/2026-10-13-claude-fable-orchestrator-demo.json`. Memo target: p50 ≤ 2 min,
  p95 ≤ 3 min (all three samples under 1:20; cold readers not measured). The earlier 1:12 figure
  (pre-release wheel, 06:xxZ) is consistent.

## Packaged demo TTFV, Track A from PyPI (the README's exact command; maintainer-machine run; AI-agent labelled)

- After publication (08:25Z): `uvx --from agent-reliability-ci arci demo` from an empty directory,
  default workers. Cold uv cache (fresh UV_CACHE_DIR): install 3 s, run 73 s, total 76 s (exit 0).
  Warm cache: install 2 s, run 97 s, total 99 s (exit 0; other processes active on the machine, not
  controlled). Installed-version check (protocol 2.3): `0.8.0 0.8.0`. Receipt:
  `docs/measurement/receipts/2026-10-13-claude-fable-orchestrator-pypi-demo.json`. Memo target
  p50 ≤ 2 min, p95 ≤ 3 min: all five Track A samples today are between 1:12 and 1:39; none is a
  cold-reader measurement.
- PyPI provenance: both files carry one PEP 740 attestation each (publisher GitHub
  ajaysurya1221/agent-reliability-ci, workflow release.yml, environment pypi), checked through
  https://pypi.org/integrity/… at 08:26Z.
