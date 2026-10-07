# agent-reliability-ci

**Did removing a retry break your agent?**

One clean run passes both versions. A transient tool timeout exposes the difference.
ARCI freezes a repeated experiment, gates the change and exports a replayable failure.

**Recorded fixture: 200 trials per arm; timeout on `reserve`.**
Baseline: **192/200**. Retry removed: **132/200**. Verdict: **BLOCK (exit 1)**.
[Recorded results](docs/results/retry-demo-n200.md) · [Trace, reduction and replay](docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt)

**Boundary:** PASS means relative non-inferiority, not absolute reliability. This is not a sandbox.
**Availability:** main adds planner and portability fixes beyond v0.7.0; no PyPI package.

**Evidence:** [18 archived decisions re-derived](docs/reports/ci-gate-2026-10-06/REPORT.md) · [Frozen contracts](FROZEN.sha256)
[Design records](docs/design/) · [CI and macOS statistics checks](.github/workflows/ci.yml)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-dark.svg">
  <img src="docs/assets/hero-light.svg" alt="arci, agent-reliability-ci: Did this change make the agent less reliable, and what broke? A frozen experiment, an exact verdict with its uncertainty, and a failure case you can replay offline. Seeded retry demo, 200 trials per arm, timeout on the first reserve call: A 192/200, B 132/200; bounds on the difference minus 0.405 to minus 0.183 against a margin of minus 0.10; VERDICT BLOCK, exit 1; 3 injected faults reduced to 1, 1-minimal; offline replay REPRODUCED. B is A with one retry removed. Source: docs/results/retry-demo-n200.md.">
</picture>

Re-derived means each archived `decision.json` regenerates byte for byte from its committed
inputs, whatever its verdict: reproducing a BLOCK, INCONCLUSIVE or ERROR counts, and no archived
run is turned green ([reproduction recipe](docs/reports/ci-gate-2026-10-06/reproduction/README.md),
[CITATION.cff](CITATION.cff)).

[![CI](https://img.shields.io/github/actions/workflow/status/ajaysurya1221/agent-reliability-ci/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/ajaysurya1221/agent-reliability-ci/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/ajaysurya1221/agent-reliability-ci?sort=semver&style=flat-square)](https://github.com/ajaysurya1221/agent-reliability-ci/releases/tag/v0.7.0)
[![Evidence package](https://img.shields.io/badge/evidence_package-2026--10--06-555?style=flat-square)](https://github.com/ajaysurya1221/agent-reliability-ci/releases/tag/evidence-2026-10-06)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square)](pyproject.toml)
[Security policy](SECURITY.md)

## Try the offline demo

Python 3.11+, POSIX and uv. Installation needs network; the fixture makes no model calls.
```bash
git clone https://github.com/ajaysurya1221/agent-reliability-ci
cd agent-reliability-ci
uv sync && .venv/bin/python examples/retry_agent/hero_demo.py
```

`just demo` runs the same script. It takes six steps through the real CLI and the Python API,
each trial in a fresh process with a separate grader process. Runtime depends on the machine and
current load. Lines from one run:

```text
=== 2. The frozen experiment, N=200 per arm, fault: tool_timeout on reserve
  VERDICT: BLOCK (exit 1)   [A vs agent_b]
  VERDICT: PASS (exit 0)   [A vs agent_a]

=== 3. Where do a passing and a failing run part ways?
  left: tool_start tool="reserve" arguments={"order_id":"order-7","quantity":2,"sku":"widget"}
  right: tool_start tool="confirm" arguments={"order_id":"order-7","sku":"widget"}
  after_injection: tool_timeout

=== 4. Shrink the failing condition (3 injected faults)
  kept: tool_timeout
  removed: empty_result, tool_error_once
  minimality: 1-minimal

=== 5. Replay the reduced bundle offline
  REPRODUCED: failure reproduced
```

Copied from the unedited, committed log
[hero-demo-2026-10-05.txt](docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt), without
the `ok` lines. Step 1 passes both agents on one clean run; step 6 passes the repaired agent C on
the exact reproducer and on its own frozen experiment; the run ends `All six steps held`, exit 0.
The experiment is also a frozen acceptance test ([test_hero.py](tests/acceptance/test_hero.py)).

Agent B is not rigged with dice. It is agent A with the retry around `reserve` removed, a plausible
refactoring slip: when `reserve` times out it carries on to `confirm` and still reports success. Its
failure rate comes from the environment. Reservations already exist with configured probability
65% (135 of the default 200 seeds, plus 8 scenarios with a naturally flaky `confirm`), and in those
the missing retry never matters. That is exactly why one run hides it.

> **Review a retry-policy change before merging**
>
> In the recorded inventory-reservation fixture, the candidate loses its retry after a timeout. ARCI reports BLOCK, locates the trace divergence, reduces three injected faults to one, and reproduces the failure offline. The repaired candidate passes the reproducer and its own separately frozen experiment.
>
> Use the example’s manifest builder as the starting point for your agent. Define the oracle, fault conditions, margin and sample size before running. A small experiment may remain INCONCLUSIVE.

Manifest builder: [examples/retry_agent/experiment.py](examples/retry_agent/experiment.py).
Recorded run: [hero-demo-2026-10-05.txt](docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt).

## Verdicts and exit codes

Every gating command ends in a verdict and an exit code. Nothing else decides.

| Verdict | Exit | Meaning |
|---|---:|---|
| `PASS` | 0 | The candidate is non-inferior to the baseline within `delta`. Nothing about absolute reliability. |
| `BLOCK` | 1 | The candidate is worse by more than `delta`, or it broke a hard invariant. |
| `INCONCLUSIVE` | 2 | Not enough evidence either way. CI stays non-green. No regression is claimed. |
| `ERROR` | 3 | The experiment is invalid: a harness or grader fault, a missing, duplicated or foreign trial, a broken seal. It can never pass. |

An agent crash, timeout, blown budget or uncaught tool fault is a `FAIL`. A broken environment,
injector, grader or event sink is an `ERROR`, and it invalidates the experiment instead of quietly
leaving the denominator. `arci replay` uses its own codes: 0 reproduced, 1 not reproduced, 3 invalid.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/where-dark.svg">
  <img src="docs/assets/where-light.svg" alt="Where arci sits. Before the run, a frozen manifest declares the baseline and candidate, oracle, faults, seeds, N and the decision rule. In CI, the recorded trials (seeded trials per arm, injected tool faults, sealed boundary records) feed the arci gate, which computes exact Clopper-Pearson bounds on the difference against a frozen margin and returns PASS, BLOCK, INCONCLUSIVE or ERROR with exit 0, 1, 2 or 3; merge on PASS, while BLOCK and ERROR fail the job and INCONCLUSIVE fails by default. A separate branch reads the same records for any verdict: trace comparison (the first divergent step between a passing and a failing trial), fault reduction (ddmin over injected faults, same failure fingerprint) and offline replay of the recorded boundary calls, not fresh model inference.">
</picture>

In words: the manifest (task, toolset, oracle, contract, both arms, fault conditions, `alpha`,
`delta`, `n_per_arm`, seeds) is sealed before the run. Each trial runs as a Python worker or a
command agent behind an MCP boundary, with a separate grader process; the tool boundary applies
budgets and seeded faults and records every call into sealed `trials.jsonl`. The gate is a pure
function of manifest and trials. Diagnosis reads the same records, whatever the verdict: `diff`
(first divergence), `minimize` (ddmin over injected faults, same failure fingerprint), `bundle`
and `replay` (re-serves recorded boundary calls: REPRODUCED, NOT_REPRODUCED or INVALID).

A Python agent is a plain function, `agent(task, tools, rng) -> dict`. It calls `tools.call("name", ...)`
and may annotate its reasoning with `tools.note_model_step(...)`. Success is decided by an oracle
over the environment's final state, never by what the agent says about itself.

**A gate that can say "I do not know".** The rule is fixed-sample and deliberately boring
([docs/STATISTICS.md](docs/STATISTICS.md)): per arm, an exact Clopper-Pearson interval at tail
`alpha / (4K)`; bounds on the difference by Bonferroni; `PASS` iff the lower bound is above
`-delta`, `BLOCK` iff the upper bound is below it. No peeking, no extending a run, no rerunning
until green. The decision rule is bound into every trial's identity, so a manifest resealed after
the run with a different rule no longer matches its trials and the gate returns `ERROR`: choosing
the rule after the data is detected, not merely forbidden. Earlier runs on the same candidate are
listed in `prior_runs` and printed in the decision and the Markdown report; `arci` does not
discover them or enforce a cross-run error budget for you. Wilson intervals are shown for
readability and never decide.

**Command agents.** An agent does not have to be a Python function: it can be any program
that speaks MCP over stdio. `arci` owns the one MCP server behind it, so every tool call is
recorded, budgeted, fault-injected and replayable from outside the agent's process.

```text
your agent (any argv) --> arci.mcp_shim --> arci.mcp_boundary --> MCP server (the environment)
                          byte relay        recorder, faults,     yours, or any python toolset via
                                            budgets, latches      python -m arci.mcp_toolset_server
```

[docs/REAL_AGENTS.md](docs/REAL_AGENTS.md) has the recipe and the local-model worked example.

**Decision calls.** A command agent may call a System One decision endpoint (TypeSafe's Jev
API). The same boundary serves `POST /v1/systemone` on loopback, records each admitted request as
a tool call named `decision:systemone`, and applies budgets, perturbations, diff, minimisation,
bundles and exact replay to it. The agent is redirected with `TYPESAFE_BASE_URL` and a per-trial token
while any real key stays in the harness; the official Python and JavaScript SDKs are exercised
unchanged by the acceptance tests. `arci preflight` checks key, endpoint, pinned model and one
smoke decision before a live run.

![The agent process, any SDK unchanged, reads two environment variables that point at a loopback port and a per-trial token. The harness-owned boundary serves the MCP tools and the decision endpoint, records every request and answer, budgets them and injects decision_low_confidence or decision_unavailable on schedule. The upstream is a seeded fixture in CI or the real API with the key held by the harness. Sealed records keep the served answer and the raw upstream answer, never the key, and feed the same gate, replay, preflight and report. Provenance: built from the vendor's documentation and both official SDKs, dated 2026-09-22; run against Jev on 2026-10-03, see docs/results/jev.](docs/images/decision-boundary.png)

**Run against Jev on 2026-10-03.** Built from documentation dated 2026-09-22, the boundary ran the
pre-registered [day one](docs/design/0004-day-one.md) live. Four things did not survive contact
and are fixed: alias-only model lists (`arci preflight --allow-unlisted-model`), smoke questions
needing `instructions`, CONNECT-only egress (`ARCI_HTTPS_PROXY`), and the console script needing
the repository root on `PYTHONPATH`. Prices and provider limits are still as documented, not
measured, and the gateway route is still untested. See [docs/DECISIONS.md](docs/DECISIONS.md).

## Where it has been run

All runs are the maintainer's own; no external users yet. Failed and invalid attempts stay in
the linked records.

- **Seeded retry demo** (2026-09-23): the result above; A against itself and the repaired C both
  PASS ([retry-demo-n200.md](docs/results/retry-demo-n200.md)).
- **Support-triage agent, live Jev endpoint** (2026-10-03, `jev-1.13.0` pinned, Python and Node
  SDKs unchanged; planted regression, the harness caps confidence and B stops escalating): A vs B
  at N=200, 200/200 vs 0/200, bounds [-1.000, -0.957], BLOCK; one minimised failure replays
  REPRODUCED; 902 recorded decisions ([docs/results/jev](docs/results/jev/README.md)). Offline
  against a seeded fixture: `.venv/bin/python examples/jev_triage_agent/hero_demo.py --n 50`.
- **The tool-call guard of the maintainer's other project, frontier-scout** (2026-10-05,
  `hook_runtime.py` verbatim at `58b0b17`, run through the harness boundary, not inside a
  coding-agent session; outages injected): fail-closed against fail-open under
  `decision_unavailable` at N=200, 200/200 vs 130/200, bounds [-0.4304, -0.2537], BLOCK; diffed,
  minimised (`reduced`) and replayed REPRODUCED ([docs/results/guardrail](docs/results/guardrail/README.md)).
- **A local model, one sentence of prompt** (`qwen3.5:4b-mlx` through Ollama, one machine,
  exploratory): N=400, 376/400 vs 308/400, bounds [-0.2445, -0.0921], INCONCLUSIVE; BLOCK needed
  the upper bound below -0.10 and missed by 0.008. Not re-run until it blocks
  ([docs/results](docs/results/README.md)).

**What went wrong and was kept.**

- Ollama run 1: a harness bug (tools advertised with no parameters), found from the failure
  clusters ([ollama-run1-n30-bridge-bug.md](docs/results/ollama-run1-n30-bridge-bug.md)). Run 3:
  the model server died and one ERROR trial invalidated the run
  ([ollama-run3-n400-invalid.md](docs/results/ollama-run3-n400-invalid.md)); hence
  `infra_exit_codes` (75 by default), which turns an agent's own infrastructure failure into ERROR.
- Jev attempt 1: every trial crashed on an import error, so equally broken arms "passed"; the
  invalid stores are kept in [attempt-1-invalid](docs/results/jev/2026-10-03/attempt-1-invalid/).
- Guardrail at N=50: 50/50 vs 38/50, bounds [-0.4016, -0.0348], INCONCLUSIVE against the
  pre-registered BLOCK, reported as is ([docs/results/guardrail](docs/results/guardrail/README.md)).

**Is the model's confidence something you can gate on?** A separate, pre-registered audit of
`jev-1.13.0` on CLINC150 and Banking77 answers that for intent routing, not permission
calibration: zero-shot accuracy 0.921 with ECE 0.024 on CLINC150, and 0.801 with ECE 0.084 on
Banking77, where confidence is over-stated in the middle of the range. Write-up, full table and
limits: [docs/results/jev-calibration](docs/results/jev-calibration/README.md); protocol and code:
[bench/jev_calibration](bench/jev_calibration/PROTOCOL.md).

## The gate, measured against itself

`just selfcheck` (or `.venv/bin/python bench/selfcheck.py`) computes the gate's own operating
characteristics by exact enumeration (`alpha` 0.05, `delta` 0.10, one condition). Probabilities of
PASS / BLOCK / INCONCLUSIVE:

| baseline -> candidate | N=20 | N=100 | N=200 | N=400 |
|---|---|---|---|---|
| 0.95 -> 0.95 | .000 / .000 / 1.000 | .443 / .000 / .557 | .889 / .000 / .111 | .999 / .000 / .001 |
| 0.95 -> 0.85 (the margin) | .000 / .000 / 1.000 | .001 / .000 / .999 | .001 / .000 / .999 | .001 / .001 / .999 |
| 0.95 -> 0.75 | .000 / .000 / 1.000 | .000 / .093 / .907 | .000 / .365 / .635 | .000 / .828 / .172 |
| 0.95 -> 0.65 | .000 / .008 / .992 | .000 / .685 / .315 | .000 / .985 / .015 | .000 / 1.000 / .000 |
| 0.80 -> 0.80 | .003 / .000 / .997 | .059 / .000 / .941 | .218 / .000 / .782 | .615 / .000 / .385 |

![Verdict probabilities by exact enumeration for the default gate: a 95 to 65 percent drop is INCONCLUSIVE 99.2 percent of the time at N=20 and BLOCK 98.5 percent at N=200; a 95 to 75 percent drop is BLOCK 36.5 percent at N=200; two equal 80 percent agents PASS 21.8 percent at N=200.](docs/images/calibration.png)

- False PASS at the margin and false BLOCK under no change are both far below `alpha` (worst
  0.004 and 0.001 over the boundary sweep). The price is conservatism: two equal agents at 80%
  reach PASS only 21.8% of the time at N=200.
- **Twenty runs decide almost nothing.** At N=20 a 95% -> 65% collapse is still INCONCLUSIVE 99.2%
  of the time, and showing a failure rate below 0.5% needs at least 598 clean trials. A
  twenty-point drop from 0.95 to 0.75 BLOCKs only 36.5% of the time at N=200.
- `interval_method: newcombe` (about twice the power, calibrated by exact enumeration rather than
  proved) and pre-registered `looks` must be frozen before the run; `arci plan` shows a design's
  verdict probabilities before you spend trials. Details: [docs/STATISTICS.md](docs/STATISTICS.md),
  [report section 3](docs/reports/ci-gate-2026-10-06/REPORT.md#3-operating-characteristics).

## Gate your own agent

A manifest is a sealed JSON document built in Python. The retry example's builder,
[examples/retry_agent/experiment.py](examples/retry_agent/experiment.py), is the template; its shape:

```python
Manifest.create(
    experiment_id="retry-agent-agent_b-reserve-timeout-200",
    task_id="confirm-inventory-order",
    task={"order_id": "order-7", "sku": "widget", "quantity": 2, "stock": 10},
    toolset="examples.retry_agent.world:make_world",  # (task, seed) -> tools + snapshot
    contract=ContractSpec(
        oracle="examples.retry_agent.world:oracle"
    ),  # (task, final_state) -> bool
    baseline=ArmSpec(label="agent_a", agent="examples.retry_agent.agents:agent_a"),
    candidate=ArmSpec(label="agent_b", agent="examples.retry_agent.agents:agent_b"),
    conditions=(
        Condition(
            condition_id="reserve-timeout",
            faults=(
                FaultSpec(
                    name="tool_timeout", bucket=Bucket.FALSIFY, tool="reserve", at_occurrence=0
                ),
            ),
        ),
    ),
    n_per_arm=200,
    base_seed=12_000,
    budgets=Budgets(max_tool_calls=10, max_model_steps=10, max_seconds=15.0),
)
```

A behaviour contract names the oracle plus the invariants the tool boundary can observe
(`max_tool_calls`, `forbidden_tools`, `required_tools`, `max_calls_per_tool`). A contract that asks
for something the boundary cannot see is rejected, not silently skipped. Fault conditions are tagged
`falsify` (a robust agent should survive), `benign` (must not change the outcome) or `ceiling`
(known-unrecoverable: reported, never gated on rates). Built in: `tool_timeout`, `tool_error_once`
and `empty_result` at the tool boundary, plus `decision_low_confidence` and `decision_unavailable`
at the decision boundary; a `"module:function"` reference plugs in your own. For a command agent,
replace `toolset` with `mcp_server` and the arms' `agent` with `command`, as
[docs/REAL_AGENTS.md](docs/REAL_AGENTS.md) shows.

```bash
arci plan --help                                   # verdict probabilities of a design, before any trial
arci preflight manifest.json                       # live decision upstreams: key, model, smoke call
arci run manifest.json --out runs --workers 8      # run + gate; exit code is the verdict
arci gate runs/<experiment> --junit junit.xml --markdown report.md
arci report runs/<experiment>                      # gate, failure clusters, tokens, estimated cost
arci diff runs/<experiment> <passing_trial> <failing_trial>    # --all-steps to include annotations
arci minimize runs/<experiment> <failing_trial> --out min.json
arci bundle runs/<experiment> <failing_trial> --out bundle.json --root . --include my_agent.py
arci replay bundle.json                            # 0 reproduced, 1 not reproduced, 3 invalid
```

A run store is one directory per experiment with the sealed manifest, `events.jsonl` and
`trials.jsonl`. Keep it with the evidence it supports; it can hold the agent's full task state and,
for decision calls, the full request state, so treat stores and bundles as sensitive data. Records
sealed by an earlier schema version are not readable after an upgrade (v0.2 and v0.5 changed the
schema); re-run the experiment rather than trust an unreadable store.

### GitHub Actions

This example pins `v0.7.0`, the released feature set. The planner (`arci plan`) and the later
portability fixes are not in that tag; see the Unreleased section of [CHANGELOG.md](CHANGELOG.md).

```yaml
- uses: actions/setup-python@v7
  with: { python-version: "3.12" }
- run: pip install -e .            # your agent, importable
- uses: ajaysurya1221/agent-reliability-ci@v0.7.0
  id: gate
  with:
    manifest: reliability/manifest.json
    workers: "4"                   # out: arci-runs by default
- run: echo "verdict=${{ steps.gate.outputs.verdict }}"
```

This assumes your agent's repository is checked out and installed, and that you pin action versions
you have verified. The report lands in the job summary (a start-up failure shows only in the step's
stderr). `BLOCK` and `ERROR` always fail the job; `INCONCLUSIVE` fails it unless you set
`allow-inconclusive: "true"`. The `verdict` output (`PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR`) is
there for steps that run after the gate. This repository's own CI runs the test suite and
re-derives the archived decisions; it does not run the Action itself.

## What it does not do

- **It is not a sandbox and not a security boundary.** Python agents share a process with their tool
  boundary. Command agents use a separate harness-owned MCP boundary, which is isolation from
  accident, not containment. Both assume buggy, non-hostile agent code; a hostile agent could still
  forge or bypass its record. See [docs/TRUST_MODEL.md](docs/TRUST_MODEL.md).
- **It only sees the tool boundary.** Files, network and subprocesses the agent touches directly are
  invisible, as is any decision call that does not go through the injected base URL.
- **It replays the boundary, not the model.** Deterministic replay is guaranteed for seeded,
  fixture-backed agents. A live model will not repeat itself token for token, so replaying its
  bundle is usually INVALID; what survives is the recorded trace and the reduced fault condition.
- **INCONCLUSIVE is common at small N.** That is the honest answer, not a failure of the run: at
  N=20 even a 95% -> 65% collapse is INCONCLUSIVE 99.2% of the time, and one real 400-trial run
  missed BLOCK by 0.008 and stayed INCONCLUSIVE.
- **A bundle embeds code, and replaying it runs that code.** Hashes are integrity checks, not
  signatures. Replay bundles only from sources you trust. A bundle embeds only the files you
  `--include` (the minimiser's output embeds none), so portable replay needs the referenced code and
  a compatible environment.
- **A divergence is evidence, not proof of cause.** It shows where two runs part ways.
- **The decision boundary has been run against one vendor model, on one day, on three seeded
  tickets.** The live model answered every clean decision with confidence 1.0, so the runs in
  `docs/results/jev` show the harness, the pacing, both SDKs and the gate working end to end and the
  planted regression caught; they say nothing about the model's calibration or about ambiguous
  tickets. Live answers are sampled, so live minimisation is reported as `reduced`, never
  `1-minimal`, and a decision model's confidence never enters a verdict except through the agent's
  actions.
- Command agents get one stdio MCP server (revision 2026-07-28), serial tool calls, no HTTP
  transport, no concurrent decisions.
- No importers (OTLP, Claude Code, Codex), no HTML report yet. POSIX only; Windows is untested.

**Related work:** [Documentation comparison, checked 2026-10-05; not a matched benchmark.](docs/reports/ci-gate-2026-10-06/REPORT.md#6-related-work-and-honest-positioning)

## Roadmap

Most valuable first: per-request pacing through parent IPC; counterfactual replay of recorded
decisions, if it can be done without overstating what a re-perturbed recording proves; extending
the intent-routing calibration audit to labelled coding-agent permission decisions, with a
separate protocol and explicit limits. Full list in [docs/ROADMAP.md](docs/ROADMAP.md).

## Development

**How it was built.** One maintainer, September 2026, with Claude Code and Codex as
pair-programmers (recorded in the commit trailers). The experiment design, the decision rule and
its calibration, the trust model and the acceptance tests are the maintainer's own; the retry
demo, the calibration table and the test suite reproduce from a clean clone. Issues and PRs welcome.

```bash
uv sync
just check        # ruff format --check, ruff, basedpyright strict, pytest
just frozen       # the frozen contract files are unchanged
just selfcheck    # the calibration table above
just demo
npm ci --prefix examples/jev_triage_agent   # only for the Node agent and its test (Node 20+)
python docs/assets/src/make_figures.py --check   # the README figures match their generator
```

The acceptance suite is hash-pinned in `FROZEN.sha256`. CI checks formatting, lint, strict typing
and tests on Python 3.11 and 3.14, with separate macOS statistics checks. See
[the workflow](.github/workflows/ci.yml) for coverage and
[the evidence report](docs/reports/ci-gate-2026-10-06/REPORT.md) for measured results. Design
records live in [docs/design](docs/design/), the changelog in [CHANGELOG.md](CHANGELOG.md).

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for adapted code.
