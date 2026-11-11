**Revise both records before acceptance.** CODE: review was read-only; no files, tests, or git state were changed. References below are repository-relative.

**ADR 0011 — REVISE**

**Blocking findings**

1. **CODE — Conflicting stopping rules.** `plan/exec/v2/adr-0011-draft.md:43` decides every round; `:92–97` submits multiple rounds before deciding yet rejects anything after the stopping round. Fix `rounds_per_look=1`, or define registered stage endpoints—including the final remainder—and evaluate exclusively there. `src/arci/gate.py:328–367` validates declared look endpoints.

2. **CODE — Store validation is incomplete.** Item 8 (`adr-0011-draft.md:94–97`) specifies membership but omits explicit manifest/trial seal validation and comparison against every scheduled identity and `spec_sha256`. Preserve checks equivalent to `src/arci/gate.py:41–50,275–318`; require ordinary RECORD specs so replayed envelopes cannot supply evidence.

3. **CODE — Adjacency contradicts unrestricted scheduling.** `adr-0011-draft.md:77` requires temporal adjacency, while `:94` permits arbitrary ordering. `src/arci/runner.py:1558–1578` submits individual trials, with individual pacing. Submission adjacency does not guarantee execution adjacency. Specify pair-level scheduling and what “adjacent” means.

4. **CODE — Provider classification lacks an implementable boundary.** `adr-0011-draft.md:78,188–190` promises infrastructure attribution, but Python-agent exceptions become crashes (`src/arci/worker.py:165–171`); tool exceptions become `ToolFault` (`src/arci/toolbox.py:298–306`). Specify a trusted model-call wrapper and persistent harness-error latch; exception-text matching or snapshot-only reporting is insufficient.

5. **CODE — Exact planning needs a defined probability model.** `adr-0011-draft.md:122–123` promises exact verdict probabilities from baseline rate and agreement, without specifying candidate rate/effect or heterogeneous cell laws. These inputs do not identify the distribution. Require per-cell joint laws, or explicitly label calculations as a homogeneous assumed-model projection.

**Non-blocking findings**

1. **CODE — Correct the measurement scope.** The four headline power/cost rows match `spikes/s1c/RESULTS.md:80,116,152,158`. But `adr-0011-draft.md:141` must say measured sizes **{10,20,50}**, homogeneous cases; heterogeneous losses reach 4.96 points (`RESULTS.md:200–201,229`). The boundary maxima come from `reviews/S1c-review-workflow.json:69`, not the two cited RESULTS files.
2. **CODE — Remove stale budget language.** `adr-0011-draft.md:175–176` retains `max_pairs` and floor-budget conclusions inconsistent with `ceil(400/N)` at `:126`. The table uses 400 pairs/800 sessions; the 400-session v1 comparison is a separate, sampled-design experiment (`spikes/s1b/RESULTS.md:132–175`).
3. **CODE — Qualify release claims.** “2.5%” applies at default alpha and to statistical BLOCK. “Less available means ERROR” is false below the tolerated-error cap. Hashes detect inconsistent records, not authenticated execution (`docs/COMPATIBILITY.md:26–28`).

**Direct answers**

1. **CODE:** Item 7 works: `TrialSpec.experiment_id` is hashed (`schema.py:472`; `schedule.py:17–19`). No frozen schema/schedule edit is needed. Specify a noncircular canonical digest preimage excluding generated IDs/seeds/seals; implement a separate suite gate.
2. **OPINION:** Prefer fresh per-round/cell trial seeds for the product’s stochastic-agent evaluation. **CODE:** The seed controls factory, agent RNG and fault RNG (`worker.py:132–150`; `toolbox.py:278,322`). Fixed seeds repeat deterministic fixtures. **KNOWN — conditional versus unconditional inference:** Fixed seeds support the narrow registered-scenario guarantee; fresh seeds require a guarantee averaging over honestly sampled seeds, not conditional on every realized seed schedule. Deterministic hashing alone supplies no randomization theorem. Live models still require the stated independence assumptions.
3. **KNOWN — pathwise domination:** Worst-case scoring is sound under the underlying outcome assumptions. **OPINION:** Keep the explicit 1% default; zero tolerance does not solve selective rerunning. Smallest rule: only a trusted model-call wrapper marks exhausted connection/timeouts or HTTP 429/5xx as infrastructure errors; latch before propagation. Keep injected faults, tool failures, parsing failures and budgets separate.
4. **CODE:** Not guaranteed by the existing parallel pool. Pair-level scheduling requires restructuring; serial execution is the restricted alternative.
5. **OPINION:** Keep `STATISTICS_SUITE.md` alongside v1; editing “Nothing else decides” is unnecessary because that sentence names `arci.gate.decide`. **CODE:** The frozen-file list needs explicit semantic scope: `AGENT_SEMANTICS.md:17–18` mandates the v1 scheduler. The added suite section must override that applicability.
6. **KNOWN — AM–GM and Ville’s inequality:** The round-end proof is sound under its assumptions; process isolation does not establish provider independence.

**ADR 0012 — REVISE**

**Blocking findings**

1. **CODE:** A separate group does not isolate collection/type checking. CI runs all tests and unrestricted basedpyright (`.github/workflows/ci.yml:65–71`; `pyproject.toml:59,76`). Specify core exclusions/skips and mandatory adapter checks with dependencies installed.
2. **CODE:** `>=1.4` is not the verified 1.4.9 lower bound (`adr-0012-draft.md:22–24`). Resolve supported ranges and endpoint testing, including transitive API packages (`reviews/S2b-review.md:47`).

**Non-blocking/direct answer**

**OPINION:** The dependency-group approach is appropriate. The AGENTS sentence amendment is sufficient and minimal for orchestrator-approved extras; retain “No new dependencies” for workers. Clarify permission to import the extra’s transitive API packages and use them in adapter tests.

**Next:** resolve ADR 0011’s registered look endpoints first.

[exited with code 0]
