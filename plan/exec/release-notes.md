# v0.8.0 — install from PyPI, `arci demo`, `arci.yaml`, `arci init`

The onboarding release. Nothing about the decision rule, its calibration, the record schema
(`arci/0.5`) or any recorded result changed; every archived decision still re-derives byte for byte.

## Install

```bash
uvx --from agent-reliability-ci arci demo            # the recorded retry story, no clone, no model call
uv tool install agent-reliability-ci                  # the arci command
```

PyPI status: the release workflow built the wheel and the sdist from the tag, smoke-tested the wheel
on Ubuntu and macOS (Python 3.11 and 3.14) from an empty directory, and published both files to PyPI
with PEP 740 attestations through trusted publishing (run 38365660814; the publish job succeeded on
its re-run at 08:25Z, after the trusted publisher was registered).

## What is new

- **PyPI package and release pipeline.** A version tag builds the wheel and sdist once, smoke-tests
  that wheel on Ubuntu and macOS (Python 3.11 and 3.14) from an empty directory, and publishes the
  same files through PyPI trusted publishing with attestations (`.github/workflows/release.yml`,
  `docs/RELEASING.md`, design record 0005).
- **`arci demo`.** The six-step retry story from an installed wheel: the frozen experiment BLOCKs the
  candidate that dropped a retry (A 192/200 vs B 132/200 at 200 trials per arm), the failing trace is
  diffed, the three injected faults shrink to the one that matters, the reduced bundle replays
  offline, and the repaired agent passes. The demo computes its counts fresh and says whether they
  matched the recorded run; the recorded run itself is unchanged evidence
  (`docs/results/retry-demo-n200.md`, `docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt`).
- **`arci.yaml`.** A thin descriptor whose keys are the sealed manifest's fields with the same
  defaults, compiled and sealed exactly as the Python builders do; `arci run` takes it directly and
  `--out` defaults to `runs`. `arci schema` prints the JSON Schema generated from the model
  (`docs/schema/arci.schema.json`, `docs/DESCRIPTOR.md`, design record 0007).
- **`arci init`.** One command, four references (baseline, candidate, toolset, oracle), a validated,
  runnable smoke descriptor (8 trials per arm: the smallest design in which a total collapse can
  still BLOCK; expect INCONCLUSIVE). References are checked by importing them in a child process,
  the way a trial would (design record 0008).
- **Honest smoke runs.** `arci run` prints a stderr notice for designs under 100 trials per arm and
  points at `arci plan`; stdout, reports and records are unchanged.
- **The current directory is on the child import path** under the `arci` console script, as it
  already was under `python -m arci.cli` (design record 0006).
- **CI.** Wheel smoke on Ubuntu and macOS, an install-and-`--help`-only Windows job (execution stays
  unsupported on Windows), and an Action fixture that must BLOCK.
- **Measurement protocol.** `docs/measurement/`: time-to-first-verdict and cold-read protocol with a
  receipt template; failed attempts are kept; no telemetry.
- **Recipes.** `examples/recipes/python_agent` (a blank project: four references, `arci init`, the
  smoke run, `arci plan`, the confirmatory run, then `diff`, `minimize`, `replay`; `docs/recipes/python-agent.md`)
  and `examples/recipes/mcp_agent` (a stdlib JSON-RPC client against the MCP toolset bridge with a
  hand-written command-arm descriptor; `docs/recipes/mcp-inspector.md`). The Inspector preflight in
  that recipe is recorded as blocked on 2026-10-13: Inspector 2.10.1 (TypeScript SDK 1.29.0) rejects
  the bridge's protocol revision `2026-07-28`; the ARCI steps run without it.
- **README.** The first screen is the question, one sentence, two commands, what PASS means, what a
  small run means, and the boundary (design record 0009).
- Also in this version, from `main` since v0.7.0: `arci plan`, opt-in `arci report --pass-k`, the
  platform-portability fixes, the technical report package and the guardrail results.

## Recorded runs this release cites (none new)

- Seeded retry demo, 2026-09-23: 192/200 vs 132/200, bounds [-0.405, -0.183], BLOCK.
- Jev day one, 2026-10-03: 200/200 vs 0/200, BLOCK; minimised failure replays REPRODUCED.
- Guardrail, 2026-10-05: 200/200 vs 130/200, BLOCK; `guardrail-live-b-ask-provider_down-50` (50/50 vs 38/50,
  bounds [-0.4016, -0.0348]) INCONCLUSIVE, kept as is.
- Local model, N=400: 376/400 vs 308/400, INCONCLUSIVE by 0.008, not re-run.

## Measured in this release's run (orchestrator's machine, 15-core Apple Silicon)

- `examples/retry_agent/hero_demo.py --n 200` from the checkout (the same six steps): 38 s. Through `uvx --from <the 0.8.0 wheel> arci demo` in an empty
  directory, including environment creation: 80 s with a cold uv cache (9 s resolve/install + 71 s
  run), 72 s and 73 s warm. Own-agent path on the sample tree (`arci init` + `arci run` at
  N=8): 3 s to a validated INCONCLUSIVE. Receipts in `docs/measurement/receipts/`, labelled as
  maintainer-machine runs; no cold-reader measurement yet.

## Limits that have not moved

PASS is relative non-inferiority within the declared margin, never absolute reliability. Not a
sandbox. Only calls that cross the tool boundary are seen. Replay is of the boundary, not the
model. INCONCLUSIVE is common at small N and is the honest answer. POSIX only. See "What it does
not do" in the README and `docs/TRUST_MODEL.md`.

## Verify

```bash
shasum -a 256 -c SHA256SUMS                                   # the attached files
uvx --from agent-reliability-ci==0.8.0 arci demo
```

Built by release workflow run 38365660814 from tag `v0.8.0` (commit 48e60ac):

```text
10ddc6823b446edd745d7904c5ab24a2fa098a0b9313ccc2df1b3277c4212899  agent_reliability_ci-0.8.0-py3-none-any.whl
99476b7b8923724eeb6392f7fa37ba4189c6fc5bb40d2ce9f10d7b3d578a9a01  agent_reliability_ci-0.8.0.tar.gz
```

The same bytes come out of `uv build --no-sources` on a clean checkout of that commit (verified on the
maintainer's machine: identical checksums). Wheel built by hatchling 1.32.4, Metadata-Version 2.5.
