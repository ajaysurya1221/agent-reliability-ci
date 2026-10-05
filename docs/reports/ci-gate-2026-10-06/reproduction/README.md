# Reproduction of the archived failure bundles on another machine

The two committed minimised bundles seal the interpreter path of the machine that produced
them (`/home/user/agent-reliability-ci/.venv/bin/python` for the Jev campaign,
`/Users/ajay/Developer/.arci-worktrees/guardrail-live/.venv/bin/python` for the guardrail
campaign) and otherwise run module commands (`-m arci.mcp_toolset_server`,
`-m examples.<campaign>.agent`). They are not resealed to make the paths convenient; instead
the paths are recreated inside a disposable Linux container and replay runs with networking
disabled, so no model key and no live endpoint can take part.

Probe of 2026-10-05 (log: `../logs/docker-replay-probe-2026-10-05.txt`), run from the arci
checkout at main `f299854`:

```bash
docker volume create arci-repro
# stage 1: install the pinned source into the sealed Linux path (network on)
docker run --rm --platform linux/amd64 -v "$PWD":/w:ro -v arci-repro:/home/user python:3.11-slim bash -lc '
  set -e; rm -rf /home/user/agent-reliability-ci; cp -r /w /home/user/agent-reliability-ci
  cd /home/user/agent-reliability-ci && rm -rf .venv && python -m venv .venv && .venv/bin/pip install -q --no-cache-dir .'
# stage 2: replay with no network; the macOS worktree path is a symlink to the same checkout
docker run --rm --platform linux/amd64 --network none -v arci-repro:/home/user python:3.11-slim bash -lc '
  mkdir -p /Users/ajay/Developer/.arci-worktrees && ln -s /home/user/agent-reliability-ci /Users/ajay/Developer/.arci-worktrees/guardrail-live
  cd /home/user/agent-reliability-ci && export PYTHONPATH=$PWD
  .venv/bin/arci replay docs/results/jev/2026-10-03/jev-live-b-low_confidence-200/min-bundle.json
  .venv/bin/arci replay docs/results/guardrail/2026-10-05/guardrail-live-b-ask-provider_down-200/min-bundle.json'
```

Observed: both replays print `REPRODUCED: failure reproduced` and exit 0 (Python 3.11.15,
glibc 2.41, linux/amd64 under emulation on an arm64 host).

## Scripted form: `reproduce.py`

`../reproduce.py` scripts this recipe and the package's other checks (standard library and the
installed `arci` only). From the repository root:

| Command | What it does |
|---|---|
| `.venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --index` | Writes `evidence-index.json` (every package file except `reproduce.py`, the index and `SHA256SUMS`, with sha256, size, what it is and what it proves; the source commit, arci version and platform; the hashes of the 18 decisions, the two bundles and the archival Ollama reports it cites) and `SHA256SUMS` (`cd docs/reports/ci-gate-2026-10-06 && shasum -a 256 -c SHA256SUMS`). Re-run after any edit to a package file. |
| `... reproduce.py` or `... reproduce.py --check` | Verifies `SHA256SUMS` and the index's external hashes; re-derives all 18 archived `docs/results/**/decision.json` byte for byte with matching exit codes (copies of `manifest.json` and `trials.jsonl`, `python -m arci.cli gate` in a subprocess, `TYPESAFE_API_KEY`, `jev_key` and `GITHUB_STEP_SUMMARY` removed from the environment, 30 s each); regenerates `metrics/plan-0.95-vs-0.75.{json,md}` with `arci plan` (the flags of the acceptance command in `../PLAN.md`) and compares bytes. An `arci` without `plan` fails this step; nothing is skipped. |
| `... reproduce.py --check --full` | Also regenerates `metrics/selfcheck-{clopper_pearson,newcombe}.json` with `bench/selfcheck.py` (minutes; values compared exactly) and runs `docs/results/guardrail/summarize.py --check`. |
| `... reproduce.py --check --strict` | Also fails on any `<<...>>` placeholder left in `../REPORT.md` (without `--strict`, the `REPRO`, `WP3` and `PLANNER` families are reported as tolerated). |
| `... reproduce.py --docker` | Runs the two stages above (volume `arci-repro` recreated; the source is the checkout's tracked and non-ignored files, so `.venv` is not copied; `pytest` pinned to the `uv.lock` version is added in stage 1), then with `--network none` replays both bundles, runs the 18 byte-exact tests and an in-container `reproduce.py --check`; writes `../logs/docker-reproduce-<date>.txt` with the source commit, uncommitted changes, image digest, interpreter and `pip freeze`. Re-run `--index` afterwards. |

Exit codes: 0 when every row is ok, 1 on any mismatch or failed step, 2 on a usage error. The
fast guard `tests/unit/reports/test_ci_gate_package.py` checks the index, `SHA256SUMS` and the
placeholder families; `ARCI_REPORT_STRICT=1` makes it tolerate no placeholder (release mode).
