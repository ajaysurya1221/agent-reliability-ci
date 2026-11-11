# ARCI v2.0 engineering plan

Source: `plan/research/arci-research-10112026.md`, checked on 10 Nov 2026 against the code at
`cdd9edb` (v1.0.0), primary sources on the web, and a read-only Codex Astra 6 consult.
Status: consolidated. Codex's findings are folded in and summarised in section 9.

## Context

ARCI v1.0.0 is solid engineering with zero adoption (0 stars, 0 issues, nothing announced).
The research recommends a v2 that plugs into agent frameworks, cuts the number of runs with
paired and sequential statistics, and ships a shareable result plus a study.

I accept that direction as the working hypothesis. I do not accept the document's specifics:
it has no links, several claims failed verification, and two of its proposals are impossible as
written. This plan keeps the direction, replaces the unverified parts with checked facts, and
puts a short proof phase in front of any product code.

Decisions you made on 10 Nov 2026: LangChain agents first; study spend capped at USD 50; you
will post the launch drafts yourself.

## 0. Research review: what holds and what does not

| Research claim | Status | Consequence for the plan |
|---|---|---|
| No maintained open-source tool combines tool-fault injection with a statistical baseline-vs-candidate gate | **Confirmed.** agentrial does unpaired statistics (stale since Feb), agentic-chaos does faults without statistics (active, 83 stars) | The niche is open. Proceed. |
| LangChain is a workable integration point | **Confirmed.** LangChain 1.4.9: `AgentMiddleware.wrap_tool_call` can raise, substitute a result or delay; stable since 1.0 (Oct 2025) | Build this adapter first. Works only for agents built with `create_agent(..., middleware=[...])`. |
| "Users write no environment or oracle" | **Impossible.** Without a success check there is no outcome to count | The user still writes tasks and one check function. The plan removes the toolset and signature work, not the check. |
| "One run, then an immediate verdict" | **Impossible** under any honest rule | First result is a small suite (about 20 tasks). Time-to-verdict is measured, not promised. |
| Depend on EvalSig for the statistics | **Rejected.** 6 commits on one day (May 2026), 2 stars, needs numpy + scipy + pyarrow, its sequential bound estimates sigma from the data so it is not valid under repeated looks, and it discards repeated trials | Implement the method in the standard library, citing the published results it rests on. |
| "Paired tests cut runs by about sqrt(2)", "2 to 4x fewer runs" | **Unsupported.** Pairing gains nothing when the two arms are independent on one task | No numeric saving is claimed until the calibration bench has measured it. |
| Phase 3 "add MCP server support" | **Already exists** (`mcp_shim.py`, `mcp_boundary.py`) | Dropped. Replaced by a one-hour compatibility check. |
| Break v1 compatibility | **Not needed.** Adding a field to the frozen `Manifest` would change the hash of every archived record (`schema.py:49-64` hashes all declared fields) | v2 adds new record types beside v1. Every v1 command, record and test stays byte-identical. |
| Study: GPT-4 vs GPT-4-turbo at USD 60 per million tokens | **Stale** models and prices | Models are picked from current price lists after a measured pilot. |
| AgentProof (LangGraph CI gate, five verdicts) | **Not found** | No fifth verdict. ERROR already covers "could not measure". |
| Launch signals include surveys | **Violates** the no-human-testing rule | Signals are public counters only. |
| Rename the package to `agent-reliability-ci2` | **Rejected** | Same package, version 2.0.0. |
| Demand evidence | **Thin but real.** Six dated 2026 issues about flaky eval gates in small projects; "On Randomness in Agentic Evals" (ICLR 2026) | Demand stays an assumption that only the launch can test. Section 3, phase 6 sets the stop rule. |

## 1. Objective and scope

**Objective.** A LangChain user puts an existing agent under a pre-registered regression gate
with one changed line of agent code, a task file and one check function, and gets a verdict
and a shareable report on a multi-task suite.

**In scope for v2.0.0**

1. A suite gate: many tasks, a few repeats each, paired arms, one pre-registered rule.
2. A LangChain adapter that routes tool calls through the existing recording and fault boundary.
3. Fault accounting: every report states how many declared faults actually fired.
4. A single-file HTML report and a pull-request comment from the GitHub Action.
5. One pre-registered public study on current models, within USD 50.
6. Release 2.0.0, launch drafts, and dated stop-or-continue signals.

**Out of scope (each with its reason)**

- EvalSig or any numeric dependency: see section 0.
- Multi-server or HTTP MCP proxying, and a Claude Agent SDK adapter: valuable, second target,
  decided after launch signals.
- Model-API fault injection and record/replay of model calls: replay removes the randomness the
  gate measures.
- OpenTelemetry importers and an Inspect AI plugin: observe-only, cannot inject faults.
- LLM-as-judge scoring, dashboards, hosted services: on the project's do-not-build list.
- Removing or changing anything in v1.

## 2. Technical architecture

**Principle: v2 is a layer above the frozen kernel.** Trials still run through `run_trial`,
the worker, `ToolBox`, the grader process and the fault registry, all unchanged.

```text
arci.yaml (tasks: file, check, baseline, candidate, faults, rule)
   -> descriptor compiles to a sealed SuiteManifest (new record, schema "arci-suite/1")
   -> suite schedule: pair i = (task, fault condition, seed), both arms; built from the manifest alone
   -> each trial is a frozen-schema TrialSpec run by the existing run_trial
        LangChain agent -> wrap_tool_call middleware -> ToolBox.call -> record, budget, inject fault
        grader process -> check(task, final_state) -> bool
   -> suite gate (pure function of manifest + trials): PASS / BLOCK / INCONCLUSIVE / ERROR, exit 0/1/2/3
   -> reports: Markdown, JUnit, JSON, single-file HTML; existing triage / diff / minimize / replay per trial
```

**New modules (flat, matching the current layout)**

| Module | Role | Reuses |
|---|---|---|
| `src/arci/suite_schema.py` | `SuiteManifest`, `SuiteDecision` (sealed Pydantic records) | `Sealed`, `digest_payload` from `schema.py` |
| `src/arci/suite_schedule.py` | Deterministic pair schedule from the manifest | `TrialSpec`, `spec_sha256` from `schedule.py` |
| `src/arci/suite_stats.py` | The paired decision procedure, standard library only | integer and `Fraction` arithmetic pattern from `stats.py` |
| `src/arci/suite_gate.py` | Pure decision, schedule check, early-stop verification | structure of `gate.py` (`_matches_spec`, look history) |
| `src/arci/suite_runner.py` | Runs the schedule, stops at a decisive point | `run_trial`, `ExperimentStore`, worker pool from `runner.py` |
| `src/arci/adapters/langchain.py` | Middleware, toolset factory, agent wrapper | `ToolBoxProtocol`, `ToolSetFactory`, `AgentFn` from `interfaces.py` |
| `src/arci/html_report.py` | Single-file HTML, no external requests | data already built in `report.py` |
| `bench/selfcheck_suite.py` | Calibration of the suite rule | pattern of `bench/selfcheck.py` |

**Changes to existing unfrozen files:** `descriptor.py` (accept `tasks:` and suite rule),
`init.py` (`--langchain` scaffold), `cli.py` (dispatch on store kind), `report.py`,
`triage.py` (resolve partners through the suite schedule), `action.yml` (PR comment).

**Binding the rule before the run, with no frozen edit.** The suite's `experiment_id` embeds
the digest of the suite rule and task set. `experiment_id` is part of every `TrialSpec`, so it
is part of every `spec_sha256`. A manifest resealed with a different rule no longer matches
its trials and the suite gate returns ERROR. Same guarantee as v1, same mechanism.

**Statistical design (proposal; frozen by ADR 0011 at the end of phase 0)**

- Unit: a pre-registered grid of T tasks by K fault conditions. One pooled estimand: the
  uniform-weight mean difference in success probability, candidate minus baseline. One
  estimand means no multiplicity correction. Verdicts and margin `delta` as in v1.
- Randomness model, stated as the contract: pair i draws its (task, condition) cell uniformly
  and independently from the grid, by a schedule derived from the sealed manifest alone; both
  arms of the pair run as fresh processes. The paired difference d is in {-1, 0, +1}.
- Procedure, one method only: two one-sided betting tests at alpha/2 each on the shifted
  difference `d + delta` (Waudby-Smith and Ramdas 2023; error control by Ville's inequality).
  PASS when the "worse than the margin" hypothesis is rejected, BLOCK when the "not worse than
  the margin" hypothesis is rejected. Valid at every stopping point, so no alpha split across
  looks. No interval inversion is needed for the verdict.
- Stopping: evaluated in schedule order at pre-registered checkpoints of `batch` pairs; the
  run stops at the first decisive checkpoint; INCONCLUSIVE only at the pre-registered
  `max_pairs`. The store must hold exactly the pairs up to the stopping checkpoint.
- Determinism: pre-registered rational stakes, `Fraction` wealth, integer threshold
  comparison, cross-platform golden vectors. No `log` or `sqrt` in the decision path.
- What voids the guarantee, each detected or disclosed: an omitted or errored pair (ERROR),
  a rule or task set changed after the run (ERROR through trial identity), rerunning with new
  seeds until green (`prior_runs` reported, not enforced), provider drift during a run
  (disclosed limit).
- Per-task and per-condition tables are descriptive only. A candidate hard-invariant violation
  still BLOCKs.
- Planning estimate from the Codex consult, not yet verified: about 104 pairs to PASS at
  0.95 vs 0.95 and about 183 pairs to BLOCK at 0.95 vs 0.75, with no capped runs. For
  comparison the v1 default at 200 pairs decides those cases 89% and 37% of the time.
- The release must not claim: universal sample savings, a decision on the first run,
  per-task non-inferiority, reliability on unseen tasks, deterministic live inference, or
  that a new campaign resets the error budget. A suite-mean PASS can hide a regression in one
  task; the per-task table sits next to the verdict for that reason.

**Dependencies.** Core runtime stays `pydantic` + `pyyaml`. LangChain arrives as the optional
extra `agent-reliability-ci[langchain]` and as a dev dependency for offline tests. This edits
frozen `pyproject.toml`, `uv.lock` and one sentence of `AGENTS.md`, authorised by ADR 0012.

## 3. Implementation phases

Sizes are orchestrated working time (Fable directing Codex), based on v0.8.0: twelve tasks in
about 5.5 hours. CI adds about 21 minutes per merge.

### Phase 0: proofs before product code (about 6 hours; no `src/` changes)

| Task | Deliverable | Pass condition |
|---|---|---|
| S1 statistics prototype | `plan/exec/v2/spikes/suite_stats_sim.py`, a results table, and a one-page statement of the sampling contract matched line by line to the theorem's assumptions | Over the grid (T in 10/20/50/100; equal and mixed task difficulty; independent, positively and negatively correlated arms) the upper 99% bound on simulated false-PASS and false-BLOCK is at or below alpha. All verdict probabilities and stopping quantiles recorded for 0.95 vs 0.95, 0.95 vs 0.75 and 0.80 vs 0.80. Small cases cross-checked by exact absorbing-state enumeration. Simulation supports the proof; it does not replace it. |
| S2 adapter spike | `plan/exec/v2/spikes/langchain_spike.py` | With LangChain's fake chat model and no network, one trial goes the whole way: tool calls recorded, each of the three faults fires, the budget is enforced, the agent's output reaches the grader through `toolset.snapshot()`, and the trial replays offline as REPRODUCED. Parallel tool calls are either serialised in a deterministic order or rejected with a clear error. |
| S3 MCP reality check | One-page note | The existing bridge is tried against one current MCP client SDK. Result recorded either way. No fix in v2.0. |
| S4 cost pilot | Token and latency table from 20 sessions per candidate model | Projected study cost at or below USD 50, or the study design shrinks until it is. Needs your API key. |
| S5 design records | ADR 0011 (suite contract and statistics), ADR 0012 (optional extra, dev dependency), each listing the exact frozen hashes that change | Codex read-only review returns no blocking finding. |

**Gate after phase 0**

- S1 fails error control, or the sampling contract cannot be matched to the theorem: stop the
  suite work. Ship the adapter and HTML report as v1.1.0 under the existing Newcombe rule.
  Phases 3, 4 and 6 still apply.
- S1 passes but shows no saving over v1 Newcombe: continue; the release claims multi-task
  support and nothing about fewer runs.
- S2 fails: the adapter target changes to Pydantic AI (`agent.override(toolsets=...)`,
  verified as a one-line hook) and you are asked first.

### Phase 1: suite decision kernel (about 5 hours; lane A)

- Build `suite_schema.py`, `suite_schedule.py`, `suite_stats.py`, `suite_gate.py`,
  `bench/selfcheck_suite.py`, `docs/STATISTICS_SUITE.md`.
- Pure code, no process spawning.
- Acceptance: unit and property tests under `tests/unit/suite/`; `selfcheck_suite.py` exits 0;
  decisions are byte-identical on Ubuntu and macOS in CI; a resealed rule, a missing trial, a
  duplicated trial and a run padded past a decisive stop each yield ERROR.

### Phase 2: suite runner, store and CLI (about 7 hours; lane A, after phase 1)

- Build `suite_runner.py`; extend `descriptor.py`, `cli.py`, `report.py`, `triage.py`,
  `diff.py` loading.
- Suite stores are supported by `run`, `gate`, `report`, `triage` and `diff` in v2.0.
  `minimize`, `bundle`, `replay` and `trace-check` on suite stores are deferred to v2.1 and
  exit 3 with a message that says so. They keep working on v1 stores.
- A 20-task seeded fixture with no model call, extending `src/arci/demo/`.
- Acceptance: `arci run` on the fixture gives BLOCK for the planted regression, PASS for the
  control and INCONCLUSIVE for a deliberately tiny `max_pairs`, with exit codes 1, 0, 2;
  `arci gate` re-derives the same sealed decision from the store; `arci triage` and `diff`
  work on a suite trial; all 1,404 existing tests pass unmodified;
  `reproduce.py --check --strict` stays 6 of 6.

### Phase 3: LangChain adapter and scaffold (about 5 hours; lane B, parallel with phases 1 and 2)

- Build `adapters/langchain.py`, `arci init --langchain`, `examples/langchain_quickstart/`,
  `docs/recipes/langchain.md`.
- Scope of the first adapter: synchronous agents, serial tool execution, JSON-serialisable
  arguments and results. Async agents, concurrent tools, `Command` returns and tool artifacts
  are rejected with a clear error, not silently passed through.
- Each tool executes exactly once per call; the middleware never re-enters the handler.
- The agent's final output is captured in trial-local state and exposed by
  `toolset.snapshot()`, because the grader only ever sees the snapshot.
- Add fault accounting to reports ("declared 3 faults, fired 3"); a declared fault that never
  fires is flagged.
- Works with v1 single-task manifests too, so it does not depend on lane A.
- Acceptance: offline tests with fake chat models under `tests/unit/adapters/`; the example
  runs end to end in CI; a scripted first-five-minutes check, from an empty virtual
  environment to a verdict on the example, passes and its wall-clock time is recorded.

### Phase 4: shareable result (about 3 hours; lane B, after phase 3)

- Build `html_report.py`, `arci report --html`, and a sticky PR comment in `action.yml`.
- Acceptance: the HTML is one file, byte-deterministic for a given store, contains the
  verdict, rule, per-task table and fault accounting, and references no external URL
  (checked by a parser test); the Action fixture posts and updates one comment.

### Phase 5: integration, study and release (about 8 hours plus study run time)

1. Merge lanes; `arci init --langchain` scaffolds a suite by default.
2. Pre-register the study: manifest sealed and committed before any trial; expectation written
   down; spend cap set in ARCI budgets and in the provider console.
3. Run the study. Keep every attempt, including invalid ones. Generate the report with the
   phase 4 tooling into `docs/results/`.
4. Re-freeze per `docs/RELEASING.md`: ADRs, `pyproject.toml`, `uv.lock`, `FROZEN.sha256`;
   README first screen under a new ADR (it is contracted by ADR 0009).
5. Tag v2.0.0; the existing release workflow builds, smoke-tests and publishes; verify PyPI
   bytes against `SHA256SUMS`.

Study design (proposal): the unmodified example agent from phase 3 on a 30 to 50 task suite
over the seeded inventory environment, baseline and candidate being two current small hosted
models from one provider, under the three built-in tool faults. The outcome is published
whatever it is.

### Phase 6: launch and measurement (30 calendar days; about 2 hours of work)

- Drafts written into `plan/exec/HUMAN_INBOX.md`; you post them.
- A script snapshots GitHub stars, unique visitors, external issues and PyPI downloads on
  days 7, 14 and 30 into `plan/exec/v2/signals/`.
- Pre-registered thresholds (assumptions; change them before launch, not after):
  day 7, at least 25 stars and 300 unique visitors; day 30, at least 100 stars and 3 issues
  or discussions opened by other people.
- Day 30 misses both: feature work stops and a retrospective is written. Either is met: the
  second target (MCP proxy or Claude Agent SDK) is planned from what people asked for.

## 4. Engineering tasks and dependencies

```text
P0: S1, S2, S3, S4 in parallel -> S5 -> gate
Lane A: P1 -> P2
Lane B: P3 -> P4            (parallel with lane A; disjoint files)
P5: needs P2 and P4        P6: needs P5 and your posts
```

At most two Codex lanes at once, with non-overlapping file ownership. Each task gets a brief
under `plan/exec/v2/tasks/` naming owned files, acceptance commands and the frozen-file rule.

## 5. Key decisions

| Decision | Choice | Why |
|---|---|---|
| Compatibility | Additive 2.0.0; v1 untouched | Breaking buys nothing and would invalidate archived evidence hashes |
| Statistics engine | Own standard-library code on published methods | EvalSig failed verification; two-dependency core is an asset |
| Unit of analysis | Suite mean, paired, tasks pre-registered | Matches how teams evaluate; where pairing actually helps |
| First adapter | LangChain middleware | Your decision; verified hook; stable API |
| Oracle | Kept: one user-written check function | Honest grading cannot be removed |
| Verdict set | Unchanged four verdicts | The "fifth verdict" source could not be found |
| Efficiency claim | Only what the calibration bench measures | Project honesty rules |
| Roles | Fable 5.2 high plans, briefs, reviews, merges, owns git; Codex Astra 6 high implements in worktrees and consults read-only at design gates | Your instruction; different-vendor review of every diff |

## 6. Risks and unknowns

| Risk | Type | Handling |
|---|---|---|
| The sampling code does not match the theorem's assumptions (Codex's top risk) | Risk | S1 delivers the assumption-by-assumption contract; ADR 0011 freezes it; the gate rejects any store that departs from the schedule |
| The test is valid but too conservative to beat v1 at small suites | Unknown until S1 | Phase 0 gate; claim adjusts to the measurement |
| Uniform draws leave some tasks unsampled in a short run | Known trade-off | Accepted for v2.0 because balanced sampling needs a different proof; the report lists unsampled cells |
| LangChain runs tool calls in parallel; `ToolBox` has no locks and replay consumes calls in order (`toolbox.py:95`, `:258`) | Confirmed in code | Serial-only adapter in v2.0; S2 proves the ordering is deterministic |
| Fake-model tests say nothing about live-model replay | Known limit | Stated in the recipe; the study records what replays and what does not |
| A user's tools touch real systems that cannot be reset per trial | Known limit | Documented; scaffold warns; out of scope to solve |
| Real-model sessions cost more than the pilot predicts | Risk | Hard caps in ARCI budgets and provider console; study shrinks |
| Demand is unproven | Assumption | Only phase 6 tests it; stop rule is pre-registered |
| Frozen-file amendments grow beyond the two ADRs | Risk | Each ADR lists exact hashes; anything else stops and is reported |
| Float differences across platforms change a decision | Risk | Integer and `Fraction` arithmetic in the decision path; cross-OS CI check |

Gaps the research left open, now assigned: which sampling scheme (S1), real cost (S4),
whether the MCP path works with today's clients (S3), what a first-time user must still write
(phase 3 documents it).

## 7. Testing and validation

- Every phase has machine-checkable acceptance above. No human testing anywhere.
- Per merge: `.venv/bin/pytest`, `ruff format`, `ruff check`, `basedpyright` clean;
  `shasum -a 256 -c FROZEN.sha256`; hosted CI on Ubuntu and macOS.
- v1 is protected by three checks that must stay green unchanged: the 1,404-test suite,
  `reproduce.py --check --strict`, and the wheel smoke script.
- Statistical claims are validated by `bench/selfcheck_suite.py`, which fails the build if any
  directional error exceeds alpha.
- Release: wheel smoke on four OS and Python pairs, PyPI bytes matched to `SHA256SUMS`.
- The orchestrator re-runs every acceptance command itself; a coder's report is not evidence.

## 8. Critical files

Read before any brief is written: `AGENTS.md`, `FROZEN.sha256`, `docs/STATISTICS.md`,
`docs/AGENT_SEMANTICS.md`, `docs/COMPATIBILITY.md`, `docs/RELEASING.md`,
`src/arci/interfaces.py`, `src/arci/schema.py`, `src/arci/schedule.py`, `src/arci/gate.py`,
`src/arci/runner.py`, `src/arci/toolbox.py`, `src/arci/worker.py`, `src/arci/triage.py`.

## 9. Codex Astra 6 consult (read-only, high effort, 10 Nov 2026)

Codex read the frozen files, gate, runner, toolbox, storage and triage, and verified all 54
frozen hashes. It changed nothing and ran no tests.

| Codex finding | Basis | What the plan does |
|---|---|---|
| Separate suite records are right; adding `tasks[]` to `Manifest` is not hash-compatible | Code: `schema.py:49`, `CHANGELOG.md:256` | Adopted (section 2) |
| The suite rule can be bound through `TrialSpec.experiment_id` into `spec_sha256` | Code: `schedule.py:17` | Adopted (section 2) |
| Define the randomness model, weighting and multiplicity before choosing the method | Opinion | Adopted: uniform independent draws, one pooled estimand, one method |
| Test the threshold directly with betting wealth; skip interval inversion | Published result plus opinion | Adopted |
| A fixed seed alone proves neither independence nor validity | Published result | Listed under what voids the guarantee |
| Exact McNemar tests equality, not a margin | Published result | Dropped as the fallback |
| `gate`, `report`, `triage`, `trace-check`, `bundle`, `minimize`, `replay` all need suite awareness | Code: `storage.py:27`, `triage.py:97`, `trace_check.py:89`, `cli.py:519` | Four commands deferred to v2.1 to keep v2.0 small |
| Adapter must start synchronous, serial, JSON-only; agent output must travel through the snapshot | Code: `toolbox.py:95`, `worker.py:149-185`, `runner.py:357` | Adopted (phase 3) |
| Cut async adapters, `Command` returns, adaptive task allocation, multiple methods | Opinion | Adopted |

One point where I go beyond Codex: its planning numbers (104 and 183 pairs) came from
illustrative fixed stakes on independent arms. I treat them as a reason to run S1, not as a
figure the release may quote.

## 10. Execution protocol

- **Fable 5.2 high (orchestrator):** writes ADRs and task briefs, owns all git operations and
  merges, reviews every diff, re-runs every acceptance command, writes the final report.
- **Codex Astra 6 high (executor and consultant):** implements one task per isolated worktree
  with `codex exec -m gpt-6-astra -c model_reasoning_effort="high"`, no git state changes, no
  network; gives read-only reviews at three gates: ADRs (phase 0), the statistics kernel
  (phase 1), and the release candidate (phase 5).
- A task that fails review twice goes back with a narrower brief; a third failure stops the
  lane and is reported to you.
- Records live under `plan/exec/v2/`: `PLAN.md`, `tasks/`, `spikes/`, `reviews/`, `consults/`,
  `DECISIONS.md`, `FINAL_REPORT.md`.
- You are needed four times: the API key for the pilot (S4), approval of the two ADRs after
  phase 0, approval to tag v2.0.0, and posting the launch drafts.

**First step after approval:** create `plan/exec/v2/PLAN.md` from this file, then brief Codex
on S1 and S2 in parallel.
