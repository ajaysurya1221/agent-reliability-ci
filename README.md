# agent-reliability-ci

![arci: regression testing for stochastic AI agents. In the seeded retry demo, one clean trial passes both agents; over 200 trials per arm with a timeout on the first reserve call, A scores 192/200 and B 132/200, bounds on the difference minus 40.5 to minus 18.3 percentage points against a margin of minus 10: VERDICT BLOCK, exit 1.](docs/images/hero.png)

**Regression testing for stochastic AI agents.** `arci` (the CLI of *agent-reliability-ci*) turns
"it passed when I tried it" into a frozen, repeated experiment with an honest verdict, and turns a
measured regression into a small failure case you can replay offline.

```text
Normal CI            Agent A: PASS      Agent B: PASS          ship it
arci (N=200 each)    Agent A: 192/200   Agent B: 132/200       VERDICT: BLOCK (exit 1)
                     bounds on the difference [-0.405, -0.183] against a margin of -0.10
                     first divergence: right after the injected tool_timeout on `reserve`
                     1-minimal reproducer: 3 injected faults -> 1, replays offline: REPRODUCED
                     repaired Agent C: passes the reproducer; 192/200 vs 192/200, PASS (exit 0)
```

Status: v0.6.0, [Apache-2.0](LICENSE), Python 3.11 or newer, POSIX only, not on PyPI (clone it, or
use the GitHub Action). It tests Python agents that use the declared tool boundary, any program
that speaks MCP over stdio, and command agents that call a System One decision endpoint. Built in
September 2026 as a hackathon by one person orchestrating three models; maintained, issues welcome.
Read [what it does not do](#what-it-does-not-do) before you rely on it.

## Why repetition and a threshold are not enough

Running an agent a hundred times and failing the build under 90% is the easy part, and several
tools already do it (as of September 2026: Promptfoo, LangSmith, Braintrust, Inspect AI,
pytest-repeat; check their current docs). Two things are usually missing. The first is a rule that
can admit it does not know: with 200 trials per arm, two genuinely equal agents at 80% success reach
a confident PASS only 21.8% of the time, and at 20 trials a collapse from 95% to 65% is still
INCONCLUSIVE 99.2% of the time, so a tool that only prints PASS or FAIL is mostly printing noise.
The second is everything that happens after the number moves: *which* run to look at, *where* it
went wrong, and a failure case small enough to fix against. `arci` freezes the experiment before it
runs, decides with an exact interval rather than a threshold, and then hands you the aligned trace
divergence, the minimised fault condition and a bundle that replays that failure with no model and
no network. That last step is the whole claim: **a measured regression becomes an executable,
reduced failure case.**

## Five minutes

You need [uv](https://docs.astral.sh/uv/) and, for the `just` shortcuts, [just](https://github.com/casey/just).

```bash
git clone https://github.com/ajaysurya1221/agent-reliability-ci
cd agent-reliability-ci
uv sync                                                 # needs the network once
.venv/bin/arci --help
.venv/bin/python examples/retry_agent/hero_demo.py      # or: just demo
```

The demo runs six steps through the real CLI and the Python API: 1,231 trials, each in a fresh
process with a separate grader process, no model calls. About 30 seconds on a 15-core laptop; a
2-vCPU CI runner needs several minutes.

1. One illustrative run: agents A and B both pass.
2. The frozen experiment (200 trials per arm, `tool_timeout` injected on the first `reserve` call)
   BLOCKs B and PASSes A against itself.
3. The paired trace diff names the first divergent step, right after the injected fault.
4. The fault minimiser shrinks a 3-fault condition to the one fault that matters, and only then
   calls it 1-minimal.
5. The exported bundle replays the failure offline from its recording.
6. The repaired agent C passes the exact reproducer and its own separately frozen experiment.

![Aligned traces of agents A and B: both call get_stock, both hit the injected tool_timeout on reserve; A reserves again and passes, B gives up without a reservation and fails. The failing condition shrinks from three injected faults to one, 1-minimal, and replays offline: REPRODUCED.](docs/images/trace-lanes.png)

Agent B is not rigged with dice. It is agent A with the retry around `reserve` removed, a plausible
refactoring slip: when `reserve` times out it carries on to `confirm` and still reports success. Its
failure rate comes from the environment. Reservations already exist with configured probability
65% (135 of the default 200 seeds, plus 8 scenarios with a naturally flaky `confirm`), and in those
the missing retry never matters. That is exactly why one run hides it. The three gate reports
behind the headline numbers are committed in
[docs/results/retry-demo-n200.md](docs/results/retry-demo-n200.md).

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

## The evidence

Four pieces: the demo above, a second offline demo, one real local model, and the gate measured
against itself.

### A confidence-gating regression, offline

```bash
.venv/bin/python examples/jev_triage_agent/hero_demo.py --n 50
```

A support-triage command agent asks a System One decision endpoint, then acts through MCP. Agent A
applies the confidence-gating pattern: every autonomous action needs confidence 0.6, a refund needs
0.85, and uncertainty or provider failure escalates to a human. B is the regression: it silently
returns in those cases. C restores escalation.

**The endpoint here is a seeded local fixture, not a vendor model.** No API key, no network. The
fixture is a deterministic CI example; it says nothing about any decision model's accuracy or
calibration.

Measured on 2026-09-22, about 20 s for all six steps on a 15-core laptop, N=50 per arm:

- clean pair: A and B both PASS
- A versus B under `decision_low_confidence`: 50/50 vs 0/50, bounds on the difference
  [-1.000, -0.832], BLOCK (exit 1)
- A versus A: 50/50 vs 50/50, bounds [-0.084, 0.084], PASS (exit 0)
- the minimiser keeps `decision_low_confidence` and removes the benign `empty_result`
  (1-minimal, 2 trials); the reduced bundle replays REPRODUCED with no provider running
- A versus C: 50/50 vs 50/50, PASS (exit 0)

### A real local model, one sentence of prompt

Needs [Ollama](https://ollama.com) running with `ollama pull qwen3.5:4b-mlx`; then:

```bash
.venv/bin/python -m examples.ollama_mcp_agent.experiment --n 30 --workers 3 --out runs
```

Exploratory evidence from one machine (Apple M5 Pro, 24 GB), one small local model
(`qwen3.5:4b-mlx` through Ollama, temperature 0.7, loopback only, zero API cost), one task. The two
arms differ by ONE sentence of the system prompt: A says "Retry a failed tool call up to three times
before giving up"; B says "Never call a tool twice; if a tool fails, carry on with the next step."

| Run | N per arm | A | B | Verdict | What happened |
|---|---:|---:|---:|---|---|
| 1 | 30 | 17/30 | 15/30 | INCONCLUSIVE, and meaningless | All 28 failures shared one fingerprint that was not the injected fault: the toolset bridge advertised tools with no parameters. A harness bug, found from the clusters and the trace in minutes. Fixed. |
| 2 | 30 | 29/30 | 23/30 | INCONCLUSIVE | A 20-point gap, visible by eye, bounds [-0.45, +0.11]. Small N on a real agent. |
| 3 | 400 | 172/182 | 143/183 | ERROR (invalid) | The model server died at pair 182 of 400, so 435 trials "crashed"; a shutdown race made one trial an ERROR, which invalidated the run. Both led to fixes. Counts are over trials where the agent actually ran. |
| 4 | 400 | 376/400 (94.0%) | 308/400 (77.0%) | **INCONCLUSIVE** | Clean run. 68 of B's 92 failures on the `reserve:timeout` fingerprint; B calls `reserve` 0.56 times per trial against A's 0.82. Bounds [-0.2445, -0.0921]; BLOCK needs the upper bound below -0.10. It missed by 0.008. |

Read honestly: a one-sentence prompt edit that survives a manual try cost about twenty points of
reliability under a single transient tool fault, and under the pre-registered rule even N=400 did
not confirm it. We report that and we do not re-run until it blocks. For scale only (not the gate,
not pre-registered), an ordinary Wald 95% interval on the same data is [-0.217, -0.123]. Re-analysed
under the later `newcombe` method the same counts give [-0.2178, -0.1225], which is BLOCK; the
sealed verdict of run 4 stays INCONCLUSIVE, because its manifest froze Clopper-Pearson before the
run. Twice the experiment was wrong rather than the agent, and both times the tool now says so by
itself. Run 3 is also why a command agent can exit with `infra_exit_codes` (75 by default) to say
"my infrastructure failed, not me": that trial becomes ERROR and invalidates the experiment instead
of counting against the agent. Full write-ups in [docs/results](docs/results/).

### The gate, measured against itself

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

- False PASS at the margin and false BLOCK under no change are both far below `alpha`: worst
  directional errors over the boundary sweep are 0.004 false-PASS and 0.001 false-BLOCK. The price
  is conservatism: two equal agents at 80% reach PASS only 21.8% of the time at N=200.
- **Twenty runs decide almost nothing.** At N=20 a 95% -> 65% collapse is still INCONCLUSIVE 99.2%
  of the time. Zero failures in 20 trials still allows a 13.9% failure rate (one-sided 95%);
  showing a rate below 0.5% needs at least 598 clean trials.
- If that is too slow, `interval_method: newcombe` (v0.3) keeps the same alpha with about twice the
  power: two equal 80% agents reach PASS .706 instead of .218 at N=200, and the real 0.94 -> 0.77
  run at N=400 blocks with probability .829 instead of .372. It is calibrated by exact enumeration
  rather than proved (worst false-PASS 0.031 at N=20, 0.026 at N >= 200; worst false-BLOCK 0.027),
  and must be frozen before the run like everything else.
- Real agents make every trial expensive, so `looks: [50, 100, 200]` (v0.4) lets a run stop at a
  pre-registered look. A 0.95 -> 0.65 regression then costs 302 expected trials with
  Clopper-Pearson and 159 with Newcombe, against 400 for the fixed design; alpha is split equally
  across looks, and the gate refuses a store that ran on past a decisive look.

## How it works

![Sealed manifest, then runner plus recorder, then a pure gate with exit codes PASS 0, BLOCK 1, INCONCLUSIVE 2, ERROR 3; sealed trial records feed diff, minimize, bundle and replay. Only boundary calls are observed; not a sandbox.](docs/images/how-it-works.png)

```text
manifest (sealed, frozen before the run)
  task + toolset + independent oracle + contract
  baseline agent, candidate agent
  K fault conditions, alpha, delta, n_per_arm, seeds
        |
        v
runner: per trial, a Python worker OR a command agent + MCP boundary + server; a separate
  grader process; everything killed as process groups at the deadline
  ToolBox = the tool boundary: budgets, seeded fault injection, record / replay
  every event streams to ONE parent writer -> events.jsonl, trials.jsonl (sealed envelopes)
        |
        v
gate: pure function (manifest, trials) -> sealed decision, exit code 0 / 1 / 2 / 3
        |
        +--> diff       first divergence between a passing and a failing trial
        +--> minimize   ddmin over the injected faults, same failure fingerprint required
        +--> bundle     portable reproducer: spec + recording + embedded code + hashes
        +--> replay     REPRODUCED / NOT_REPRODUCED / INVALID
```

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

**Command agents (v0.2).** An agent does not have to be a Python function: it can be any program
that speaks MCP over stdio. `arci` owns the one MCP server behind it, so every tool call is
recorded, budgeted, fault-injected and replayable from outside the agent's process.

```text
your agent (any argv) --> arci.mcp_shim --> arci.mcp_boundary --> MCP server (the environment)
                          byte relay        recorder, faults,     yours, or any python toolset via
                                            budgets, latches      python -m arci.mcp_toolset_server
```

[docs/REAL_AGENTS.md](docs/REAL_AGENTS.md) has the recipe and the local-model worked example.

**Decision calls (v0.5, v0.6).** A command agent may call a System One decision endpoint
(TypeSafe's Jev API). The same harness-owned boundary serves `POST /v1/systemone` on loopback,
records each admitted request as a tool call named `decision:systemone`, and applies budgets,
perturbations, diff, minimisation, bundles and exact replay to it. The agent is redirected with
`TYPESAFE_BASE_URL` and a per-trial token while any real key stays in the harness; the official
Python and JavaScript SDKs are exercised unchanged by the acceptance tests. `arci preflight` checks
the key, the endpoint, the pinned model and one smoke decision before a live run; `run` paces
trial starts for HTTP upstreams; `report` shows recorded decisions, tokens and an estimated cost.

![The agent process, any SDK unchanged, reads two environment variables that point at a loopback port and a per-trial token. The harness-owned boundary serves the MCP tools and the decision endpoint, records every request and answer, budgets them and injects decision_low_confidence or decision_unavailable on schedule. The upstream is a seeded fixture in CI or the real API with the key held by the harness. Sealed records keep the served answer and the raw upstream answer, never the key, and feed the same gate, replay, preflight and report. Provenance: built from the vendor's documentation and both official SDKs, dated 2026-09-22; Jev was not run.](docs/images/decision-boundary.png)

**This path has never been run against a vendor decision model.** v0.5 and v0.6 were built from
vendor and official SDK documentation dated 2026-09-22 and are tested against seeded fixtures and
fake upstreams shaped like that documentation; no key was available. Treat the gateway behaviour,
model identifiers, prices and provider limits as documented, not verified. See
[docs/DECISIONS.md](docs/DECISIONS.md).

## Gate your own agent

A manifest is a sealed JSON document built in Python. The retry example's builder,
[examples/retry_agent/experiment.py](examples/retry_agent/experiment.py), is the template; its shape:

```python
Manifest.create(
    experiment_id="retry-agent-agent_b-reserve-timeout-200",
    task_id="confirm-inventory-order",
    task={"order_id": "order-7", "sku": "widget", "quantity": 2, "stock": 10},
    toolset="examples.retry_agent.world:make_world",       # (task, seed) -> tools + snapshot
    contract=ContractSpec(oracle="examples.retry_agent.world:oracle"),  # (task, final_state) -> bool
    baseline=ArmSpec(label="agent_a", agent="examples.retry_agent.agents:agent_a"),
    candidate=ArmSpec(label="agent_b", agent="examples.retry_agent.agents:agent_b"),
    conditions=(Condition(condition_id="reserve-timeout", faults=(
        FaultSpec(name="tool_timeout", bucket=Bucket.FALSIFY, tool="reserve", at_occurrence=0),)),),
    n_per_arm=200, base_seed=12_000,
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

```yaml
- uses: actions/setup-python@v7
  with: { python-version: "3.12" }
- run: pip install -e .            # your agent, importable
- uses: ajaysurya1221/agent-reliability-ci@v0.6.0
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
there for steps that run after the gate.

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
- **The decision boundary is untested against a real vendor model.** Everything in v0.5 and v0.6 was
  derived from documentation and exercised against fixtures and fake upstreams. Live answers are
  sampled, so live minimisation is reported as `reduced`, never `1-minimal`, and a decision model's
  confidence never enters a verdict except through the agent's actions.
- Command agents get one stdio MCP server (revision 2026-07-28), serial tool calls, no HTTP
  transport, no concurrent decisions.
- No importers (OTLP, Claude Code, Codex), no HTML report yet. POSIX only; Windows is untested.

## Roadmap

Most valuable first: per-request pacing through parent IPC instead of the divide-by-k trial-start
approximation; counterfactual replay of recorded decisions, if it can be done without overstating
what a re-perturbed recording proves; an independent calibration audit of decision models on exact
intervals (needs labelled real outputs and a key); a System One emulator over a local model;
streamable HTTP transport and several MCP servers per trial; importers built only from authentic
versioned fixtures; cohort localisation across all passing and failing trials; task-clustered
aggregation; then a SQLite index, resumable runs, an HTML report and a larger perturbation library.
Full list in [docs/ROADMAP.md](docs/ROADMAP.md).

## Development

```bash
uv sync
just check        # ruff format --check, ruff, basedpyright strict, pytest
just frozen       # the frozen contract files are unchanged
just selfcheck    # the calibration table above
just demo
npm ci --prefix examples/jev_triage_agent   # only for the Node agent and its test (Node 20+)
```

The acceptance suite under `tests/acceptance/` is the specification, hash-pinned in `FROZEN.sha256`.
It was written before the implementation and hardened by an adversarial reviewer at every release:
about 45 findings in four rounds at v0.1, with reproductions; eleven more against the
out-of-process boundary at v0.2; five blockers each at v0.5 and v0.6, every one now a frozen
regression test. More than 430 tests and basedpyright strict; CI runs Python 3.11 and 3.14, with
Node 22 for the JavaScript SDK test. The reviewer's findings are why the trust model and the
hardening tests exist. Design records live in [docs/design](docs/design/), the changelog in
[CHANGELOG.md](CHANGELOG.md).

[Apache-2.0](LICENSE). See [NOTICE](NOTICE) for adapted code.
