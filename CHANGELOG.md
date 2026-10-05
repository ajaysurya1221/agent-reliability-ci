# Changelog

## Unreleased

- **Fixed:** platform-dependent rounding in 95% Wilson intervals by pinning the inverse-normal
  value used by the existing Linux-produced records (CPython's C accelerator on arm64 macOS
  differs by one ulp from the pure-Python fallback). Restores reproducible decision seals for
  the archived Clopper-Pearson stores without changing any verdict. Regression tests re-derive
  every committed `docs/results/jev` decision byte for byte.
- **Fixed:** platform-dependent Clopper-Pearson bounds by comparing binomial tails with exact
  integer arithmetic, including zero-success and all-success bounds. The existing 60-step
  bisection, statistical method, confidence allocation, and gate rules are unchanged. Re-derived
  six archived Jev decisions and five guardrail decisions from unchanged sealed manifests and
  trials. Only CP bounds, their derived difference bounds, and decision seals changed; verdicts,
  exit codes, counts, stopping histories, and rendered Markdown/JUnit reports are unchanged.
  Byte-for-byte regeneration is checked on macOS and Ubuntu.
- **Guardrail experiment:** published the pre-registered live run of
  `examples/guardrail_agent/` (2026-10-05, `run.sh` unchanged): the sealed stores of all six
  runs, the preflight receipt, per-run gate reports, and the N=200 failure diffed, minimised
  and replayed (REPRODUCED), in `docs/results/guardrail/`. The write-up and `metrics.json` are
  generated from the committed evidence by `docs/results/guardrail/summarize.py`
  (`--check` fails if they are stale), including the N=50 `decision_unavailable` run that came
  out INCONCLUSIVE rather than the pre-registered BLOCK. Added
  `tests/unit/examples/test_guardrail_results.py`, an offline test that re-derives every
  committed guardrail decision byte for byte with `arci gate`.
- **Added:** `arci plan` enumerates PASS, BLOCK and INCONCLUSIVE probabilities under the
  existing Clopper-Pearson gate for independent binomial arms, one gating condition, one
  fixed-sample look and N <= 400 per arm, reporting assumptions and the smallest tested N meeting
  a target or "target not reached".
- **Added:** opt-in Markdown `arci report --pass-k` estimates using C(successes,k)/C(n,k)
  separately per arm and condition, with explicit IID assumptions and unavailability for n < k,
  ERROR verdicts and multi-look designs; default report output, gate decisions and stored records
  are unchanged.

## v0.7.0 (2026-10-03)

- **Calibration audit of the decision model (2026-10-03):** `bench/jev_calibration/` is a
  pre-registered audit of `jev-1.13.0` on CLINC150 (4,500 in-scope + 1,000 out-of-scope) and
  Banking77 (3,080), three passes each plus a bundling check, 26,140 requests, about USD 4.6
  at list price. `PROTOCOL.md` (hash posted on PR #2 before the first request) fixes the
  questions, passes, measures and seven expectations; `run.py` seals every answer in a
  hash-chained store; `metrics.py` (exact binomial intervals, ECE/MCE/Brier/log loss,
  tie-aware AUROC and average precision, bootstrap, agreement) is unit tested; `analyze.py`
  verifies the chains and writes `metrics.json`, `report.md`, reliability diagrams and a
  self-verifying compact store from which every number re-derives. All seven expectations
  met: zero-shot accuracy 0.921 [0.912, 0.928] on CLINC150 (a supervised TF-IDF+LR trained on
  15,000 examples: 0.925) with ECE 0.024; 0.801 on Banking77 with ECE 0.084 and mid-range
  over-confidence; 0.970 accuracy at confidence >= 0.9 on 83% coverage; out-of-scope AUROC
  0.977 (yes/no question) against 0.911 from 1 - p_max; 99.4% repeat agreement; p50 322 ms.
  Write-up: `docs/results/jev-calibration/README.md`.
- **Added:** `examples/jev_triage_agent/experiment.py` builds live manifests
  (`live_manifest`, `decisions.upstream = "http"`, pinned model, paced trial starts, prior
  runs) and writes them from the command line
  (`python -m examples.jev_triage_agent.experiment --out manifest.json`), so the day-one
  sequence in `docs/design/0004-day-one.md` runs from files. `examples/jev_triage_agent/day_one.sh`
  drives it end to end: preflight, the clean pair, the N=50 trio, the Node agent through the
  official SDK, the pre-registered N=200 run, and a minimised, replayed failure, with a gate
  report per run and a refusal to finish if the key appears in any output. Results:
  `docs/results/jev/`.
- **Run against Jev (2026-10-03):** the pre-registered day one ran end to end against
  `https://api.typesafe.ai` with `jev-1.13.0` pinned. A vs B under `decision_low_confidence` at
  N=200: 200/200 vs 0/200, bounds [-1.000, -0.957], BLOCK; A vs A and A vs C PASS at N=50; the
  Node agent through the unchanged official SDK BLOCK; the minimised failure replays REPRODUCED;
  an exploratory clean run at N=50 routed all 100 decisions correctly at confidence 1.0. 902
  recorded decisions, about USD 0.018 at list price. Sealed stores, the preflight receipt, the
  invalid first attempt and one write-up per run: `docs/results/jev/`; every `decision.json`
  re-derives from its committed `trials.jsonl`. Findings: `docs/DECISIONS.md`, "What day one
  found".
- **Added:** `arci preflight --allow-unlisted-model`. The account's `GET /v1/models` lists only
  the aliases `jev-latest` and `jev-preview`, so the pre-registered preflight exits 2 on a pinned
  versioned id. With the flag, preflight prints the listed names, sends the smoke request, and
  exits 0 only if the validated response reports exactly the pinned id (3 otherwise). Without the
  flag nothing changes except a hint after the exit-2 message. Tests:
  `tests/unit/cli/test_preflight_unlisted_model.py`.
- **Added:** `ARCI_HTTPS_PROXY=http://host:port` makes the decision upstream sender tunnel through
  an HTTP CONNECT proxy, for environments whose only egress is such a proxy; unset, the direct
  connection is unchanged, and a malformed value is a transport error. Tests:
  `tests/unit/decisions/test_upstream_proxy.py`.
- **Fixed:** the three preflight smoke questions carry `instructions`; the vendor rejects a
  question with neither `instructions` nor `criteria` (400), so the pre-registered smoke request
  could not be accepted as written.
- **Fixed:** `examples/jev_triage_agent/day_one.sh` puts the repository root on `PYTHONPATH`
  (the manifests name `examples.jev_triage_agent.*` modules, invisible to the `arci` console
  script), insists on running from the repository root, and stops with exit 4 unless both arms of
  the N=1 clean pair PASS, so a harness fault that breaks both arms equally cannot be mistaken
  for a measurement.
- **Fixed:** two reader threads, the grader's response reader and the MCP boundary's frame
  reader, could end a read on a "not ready" poll verdict computed before the child wrote and
  before the parent asked them to stop. On a loaded machine the thread was descheduled across
  the child's exit, the stale verdict dropped the whole response, and the trial ended `ERROR`
  (`grader returned invalid output`, or `boundary exited before returning` for command agents)
  at about 1 trial in 400 with 8 workers on 4 cores, which is enough to turn a 200-per-arm
  experiment into an `ERROR` verdict on a busy CI runner. The worker reader already followed
  the correct rule; both readers now snapshot the stop flag before polling, and only a poll
  made after the stop was observed may end the read. Regression tests:
  `tests/unit/runner/test_reader_stop_race.py`.

## v0.6.0 (2026-09-22)

Day-one Jev readiness. The upstream behavior below is derived from vendor and official SDK
documentation and tested against shaped fixtures; it was not run against Jev because no key was
available.

- **A1:** HTTP decision upstreams accept a path-prefixed base URL, including the Vercel AI Gateway
  TypeSafe route and its `typesafe-ai/jev` model id.
- **A2:** Response validation accepts the tested SDK response shapes: unknown metadata is tolerated and rounded
  probability sums are accepted within `1e-3`, while required keys and pinned-model checks remain.
- **A3:** Harness-owned request headers, allowlisted response headers, deterministic transport
  diagnostics, and one recorded bounded wait on an upstream 429/529 make gateway attempts auditable.
- **B4:** `arci preflight MANIFEST` checks credentials, model discovery and one tiny smoke decision,
  then emits a credential-free receipt with exit 0/2/3 semantics.
- **B5:** HTTP experiments pace trial starts through a shared parent token bucket; users divide the
  provider rate by the maximum decisions per trial.
- **B6:** Markdown reports count completed decision recordings and their available token usage,
  and show estimated input cost at the list price read on 2026-09-22 (fixtures and replays are
  free; this is an estimate, not billed spend). Incomplete admissions are excluded; before-injected
  results contribute zero tokens.
- **B7:** The Jev guide now covers the three-command day-one workflow, provider limits, privacy,
  sampled answers and live-run minimality; `docs/results/TEMPLATE-jev.md` standardises write-ups.
- **C8:** The triage example gains a Node 20+ ES-module agent using `@typesafe-ai/sdk` 0.6.0 through
  environment-only `new TypeSafeClient()`, plus CI coverage on Python 3.14 / Node 22.
- **C9:** Decision records retain an independent raw upstream snapshot before perturbation; live
  HTTP upstreams, removal trials ending in ERROR, and replay INVALID results report `reduced`, never
  `1-minimal`.
- **D10:** The offline triage fixture can inject seeded synthetic miscalibration for testing
  confidence gates; it is explicitly not evidence about Jev's calibration.

## v0.5.0 (2026-09-22)

Command agents can now test the decision logic around TypeSafe's Jev/System One API.

- `Manifest.decisions: DecisionSpec` adds a harness-owned loopback `POST /v1/systemone` boundary.
  Agents are redirected through `TYPESAFE_BASE_URL` and a per-trial token; the real upstream key
  stays in the harness (the MCP server child does not inherit it, diagnostics are scrubbed). The
  Python `typesafe-sdk` is exercised unchanged by the acceptance tests; the JavaScript SDK reads the
  same variables but is untested here.
- Admitted decisions use the existing `ToolCall`, `ToolResult` and `RecordedCall` records under
  `decision:systemone`, so budgets, events, diff, minimisation, bundles and exact replay apply.
- `decision_low_confidence` mixes choice probabilities toward uniform without changing the winner;
  `decision_unavailable` returns an injected 529 from a selected occurrence onward.
- The boundary now lives until the command agent exits when decisions are configured, including
  decisions made after the MCP session closes. Decision/MCP overlap and concurrent decisions are
  rejected as harness faults.
- Schema `arci/0.5` adds decision configuration to sealed manifests and trial specs. Records sealed
  by earlier schema versions are not readable; as with every field addition, experiments must be
  re-run.
- The official `typesafe-sdk` is a development-only dependency used by an acceptance test against
  the boundary. Runtime code and `examples/jev_triage_agent` do not import it.
- `examples/jev_triage_agent` is a six-step offline triage demo: a confidence-gating regression is
  blocked, reduced, replayed, and repaired. `docs/DECISIONS.md` documents fixture and real-Jev use.

## v0.4.0 (2026-09-22)

One thing: pre-registered looks, so an experiment can stop early without losing error control.

- `Manifest.looks = (N_1, ..., N_L)`: cumulative pairs per condition, last equal to `n_per_arm`.
  Equal Bonferroni spending, `alpha / L` per look, with either interval method. The run stops at
  the first look that is PASS or BLOCK; the final look is INCONCLUSIVE otherwise. No `looks` is
  the fixed design, unchanged.
- The gate replays every look and treats the first decisive one as a mandatory stop: a store that
  continued past it, stopped without a decision, or is not a whole-pair prefix at a declared look
  is ERROR. The plan is bound into every trial's identity; the look history is sealed into the
  decision.
- `bench/selfcheck.py --looks 50,100,200`: exact enumeration over sequential paths (a
  (x_A, x_B) state table, at most (N+1)^2 states), with the same false-PASS / false-BLOCK <= alpha
  sweep. Measured, K=1: a 0.95 -> 0.65 regression costs 302 expected trials with Clopper-Pearson
  (P(BLOCK) .985 -> .943) and 159 with Newcombe, against 400 for the fixed design; two equal 0.95
  agents cost 350 and 239. The Markdown report shows the look history and the stopping look.

## v0.3.0 (2026-09-22)

One thing: a tighter interval for the margin, opt-in.

- `Manifest.interval_method`: `clopper_pearson` (default, unchanged) or `newcombe` (Newcombe's
  hybrid score interval, method 10, no continuity correction, Wilson per arm at `1 - alpha/K`).
  Frozen with the manifest; printed in every decision and report.
- Calibration by exact enumeration in `bench/selfcheck.py --method newcombe`: a sweep of the
  boundary and the no-change line for p in [0.5, 0.99], N in {20, 50, 100, 200, 400}. Worst
  directional error 0.031 (alpha 0.05). The bench exits non-zero if any sweep fails. Head-to-head
  table in `docs/STATISTICS.md`.
- Why: the clean v0.2 confirmatory run (376/400 vs 308/400) was INCONCLUSIVE by 0.008 under the
  default rule; Clopper-Pearson with Bonferroni was spending about a tenth of its allowed alpha.
  Re-analysed under `newcombe` it blocks. Its sealed verdict stays INCONCLUSIVE.

## v0.2.0 (2026-09-21)

Command agents: test any program that speaks MCP over stdio, not only Python functions.

### Added

- **The out-of-process boundary.** A trial can be any subprocess (`CommandSpec`). Its tools are ONE
  stdio MCP server owned by the harness (`McpServerSpec`). The agent's process tree holds only a
  byte-relay shim (`arci.mcp_shim`); the recorder, fault injection, budgets and fault latches live in
  a harness-owned boundary process (`arci.mcp_boundary`). Same frame protocol, latch precedence,
  deadlines, process-group cleanup and sealed envelopes as v0.1.
- Supported MCP subset (revision 2026-07-28): `initialize`, `notifications/initialized`, `ping`,
  `tools/list`, serial `tools/call` with `resultType: "complete"`. Task results, sampling,
  elicitation and concurrent calls are a harness ERROR, never a silent pass-through.
- Replay for command agents: the recording includes `initialize` and `tools/list`, the server is
  never started, JSON-RPC ids are normalised, consumption must be exact.
- `arci.mcp_toolset_server`: serve any v0.1 python toolset as an MCP server, with a trusted
  `snapshot` for grading.
- `examples/ollama_mcp_agent`: a real tool-calling agent on a local model, with a one-sentence
  prompt regression between its arms. `docs/REAL_AGENTS.md`, `docs/design/0002-...md`.
- Schema `arci/0.2`: `ArmSpec.command`, `Manifest.mcp_server`, `McpServerSpec.snapshot`. An
  experiment is all python agents or all command agents. v0.1 run stores must be re-run.

- `CommandSpec.infra_exit_codes` (default 75, EX_TEMPFAIL): an agent can say "my infrastructure
  failed, not me". The trial is ERROR and invalidates the experiment instead of counting against the
  agent. Added after a local model server died mid-experiment and 435 trials "crashed".

### Evidence (docs/results)

A real local-LLM agent, two arms differing by one sentence of the system prompt, one injected tool
timeout. Four runs are reported, including two invalid ones that each exposed a defect (a bridge
that advertised no tool parameters; a dead model server plus a harness shutdown race). The clean
confirmatory run: 376/400 (94.0%) versus 308/400 (77.0%), bounds [-0.2445, -0.0921], verdict
INCONCLUSIVE by 0.008 under the pre-registered rule. Reported as is.

### Fixed during review

Eleven findings from an adversarial review of the boundary (false REPRODUCED at a deadline kill,
boundary crashes blamed on the agent, client mistakes invalidating experiments, malformed server
results accepted, id reuse, pipe deadlocks, recordings over 1 MiB, path leaks), a shim deadlock, and
a shutdown race that turned about 5% of trials into false ERRORs on a loaded machine.

### Trust model

For command agents the record can no longer be corrupted by accident from inside the agent's
process. This is isolation from accident, not a sandbox: the agent still holds the socket it was
given, and whatever it does outside MCP is invisible.

### Known limits

- One MCP server per trial, stdio only. No HTTP transport yet.
- Tool replay is not agent replay: a live model rarely repeats its calls, so replaying its bundle is
  usually INVALID. Deterministic replay is demonstrated only with scripted clients.
- The Claude Code recipe in `docs/REAL_AGENTS.md` is an untested sketch; no paid-agent trials were
  run for this release. The local-model results are exploratory (one machine, one small model).
- POSIX only (unix sockets, process groups).

## v0.1.0 (2026-09-21)

First release. One claim: a measured regression becomes an executable, reduced failure case.

### What is in it

- Frozen, sealed experiments (`Manifest`), a deterministic paired schedule, one fresh process per
  trial with a separate grader process, a single parent writer for `events.jsonl` and `trials.jsonl`.
- The tool boundary (`ToolBox`): budgets, seeded fault injection (`tool_timeout`, `tool_error_once`,
  `empty_result`, or your own `"module:function"`), record and replay.
- The gate: exact Clopper-Pearson at tail `alpha / (4K)`, Bonferroni bounds on the difference,
  verdicts PASS / BLOCK / INCONCLUSIVE / ERROR with exit codes 0 / 1 / 2 / 3. It never raises.
- `bench/selfcheck.py`: the gate's own operating characteristics by exact enumeration.
- Boundary-aligned trace divergence, ddmin fault minimisation with an honest 1-minimal claim,
  portable replay bundles with hash-verified embedded code.
- CLI (`arci run | gate | report | bundle | replay | diff | minimize`), Markdown and JUnit reports,
  a composite GitHub Action.
- `examples/retry_agent`: agents A, B (A minus one retry) and C (the repair), with a six-step demo.

### How it was checked

229 tests, basedpyright strict, CI on Python 3.11 and 3.14. The acceptance suite was written before
the implementation and is hash-pinned (`FROZEN.sha256`). An adversarial reviewer attacked the design and
the code in four rounds, with reproductions: about 45 findings. They were fixed, or, where out of
scope (a hostile in-process agent, detached descendants), documented as non-goals. The behavioural
fixes have frozen regression tests (`tests/acceptance/test_hardening*.py` and the gate, replay and
schema suites); documentation corrections and the protocol queue bound do not. Every published
calibration number was recomputed independently by the reviewer and matched.

### Known limits and residual risks

- Trust model: the agent is assumed buggy, not hostile. It shares a process with the tool boundary,
  so a deliberately hostile agent can forge its result. See `docs/TRUST_MODEL.md`.
- Only the tool boundary is observed. Direct file, network or subprocess use by the agent is
  invisible. Descendants that start their own session survive cleanup.
- The gate is conservative by design: mid-range success rates need large N to reach PASS, and
  N=20 decides almost nothing. `prior_runs` is author-supplied; no cross-run error budget is enforced.
- Supported statistics range: `alpha` in [1e-6, 0.5] with `alpha >= K x 1e-6`, `n_per_arm <= 10000`.
- Bundles embed only the files you include; the minimiser's output embeds none.
- The final reviewer re-check ran on Python 3.13 in a read-only sandbox, so writing bundle payloads
  to disk was exercised by the test suite and CI (3.11, 3.14) but not by that review.
- POSIX only (process groups, `ps` in tests). Windows is untested.
