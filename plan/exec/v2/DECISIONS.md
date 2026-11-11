# Decisions (ARCI v2.0)

Kept by the orchestrator. One entry per decision, newest last. A decision by the maintainer
quotes the maintainer's words.

## D-01: plan approved (2026-11-10)

The maintainer approved `PLAN.md`. LangChain agents first; public study capped at USD 50;
the maintainer posts the launch drafts.

## D-02: ADR 0011 and ADR 0012 approved (2026-11-11)

The maintainer answered "Approve both" to "Approve ADR 0011 and ADR 0012 so phases 1 and 3
can start?". The two judgment calls inside ADR 0011 were put to the maintainer in the same
message and stand as drafted:

- Seed rule default: `scenario_seeds: fixed`.
- Default `max_errored_pairs`: 1% of the registered pairs, rounded up.

The drafts stay under `plan/exec/v2/` until the phase 1 re-freeze copies them to
`docs/design/0011-suite-gate.md` and `docs/design/0012-optional-framework-extras.md`.

## D-03: orchestrator readings of ADR 0011, fixed in the phase 1 contract (2026-11-11)

ADR 0011 leaves these open. Each is the simplest reading that keeps the ADR's guarantee.
They are written into `tasks/P1-CONTRACT.md`, and Codex reviews them before any code.

1. **Cells are the full grid.** A suite manifest lists tasks and fault conditions; the cells
   are every (task, condition). No ragged grids in v2.0.
2. **What the rule digest covers.** Every field of the manifest except `experiment_id`,
   `created_at` and `record_sha256`, with tasks and conditions sorted by id. This is a
   superset of the ADR's list (it adds the contract, budgets, toolset and prior runs), so
   any change to registered content gives a new experiment id.
3. **`experiment_id` is `<suite_id>@<64 hex digest>`.** The full digest, not a prefix.
4. **Statistics-dependent limits live outside the frozen schema.** The schema checks
   structure only. The budget floor and the errored-pair limit are checked by one function
   in `suite_stats.py`, called by the runner before any trial and by the gate.
5. **"PASS unreachable" (item 10) means:** with `max_errored_pairs` pairs errored and every
   other pair won by the candidate, the PASS wealth at the last round end is below
   `2/alpha`. That is the literal reading. The stricter reading (a candidate that never
   differs) would refuse the 1% default at the minimum budget.
6. **Decision records carry counts, not wealth fractions.** Cumulative counts per round
   determine the wealth exactly. Wealth is also printed as a short decimal string for
   people; the string is derived by integer arithmetic and never compared.
7. **Suite experiments support Python agents and command agents** (the same two kinds as
   v1) but not `decisions`. The schema is hash-sealed, so a field left out now could not be
   added later without a new schema version.
8. **Total registered pairs are capped at 100,000**, ten times v1's per-arm cap.

## D-04: when the frozen files change (2026-11-11)

Lanes run against the frozen files as they are on `main`. Lane B gets LangChain in its own
virtual environment at the versions phase 0 used; `pyproject.toml` and `uv.lock` change once,
at integration (phase 5), as ADR 0012 says. New suite files become frozen at the phase 1
re-freeze, after their acceptance tests pass.

## D-05: who writes the suite acceptance tests (2026-11-11)

Codex implements the suite kernel from `tasks/P1-CONTRACT.md`. A separate Claude agent
writes the acceptance tests from the same contract without seeing Codex's code. The
orchestrator then runs those tests against the code. A disagreement is either a defect or
an ambiguity in the contract, and is settled before the re-freeze.

## D-06: the study runs on local models through Ollama (2026-11-11)

The maintainer: "Please go with Local (Ollama)". This replaces the hosted-API study and its
USD 50 cap for now: no API key, no payment. The cost pilot S4 becomes a pilot of time per
session and of tool-calling ability for candidate local models. A hosted-model study stays
possible later without code changes. Open: which two models (chosen from what is installed
or pulled with the maintainer's agreement, after the pilot).

## D-07: the orchestrator commits and pushes without asking (2026-11-11)

The maintainer: "don't wait for me for anything. Take control of the CLI for yourself and
all i need to see is something finally in our Github." From here the orchestrator commits
and pushes the v2 branches as work is verified. Still outside this: anything the
maintainer's own deny list blocks (opening or merging pull requests with `gh`), merging to
`main`, tagging and publishing a release.

## D-08: adapter rules settled after the independent review (2026-11-11)

Orchestrator decisions under D-07. Source: `reviews/P3a-review-workflow.json` (39 agents,
35 findings, none refuted).

1. **Set-up failures are ERROR, not FAIL.** Anything raised before the first model call
   (the agent settings callable, `create_agent`, `task_to_input`, the graph rejecting its
   input, async-only user middleware) is a harness error. Otherwise a broken configuration
   fails both arms alike, every pair ties, and ties count toward PASS.
2. **ADR 0011 item 10 is widened before it is frozen.** Infrastructure errors also include
   HTTP 401, 403, 407 and 408, DNS failures (`socket.gaierror`) and TLS failures
   (`ssl.SSLError`). Same reason as item 1: a missing key or dead network is not agent
   behaviour.
3. **An interrupted run is rejected.** A graph that returns with an interrupt pending is a
   harness ERROR; it was being graded as a completed run.
4. **The order gate has no fixed deadline.** A waiting tool call times out only when no
   call has been running for 30 seconds (a real deadlock). The trial's own time budget
   bounds everything else.
5. Kept as stated limits for the recipe: non-finite numbers in arguments are agent
   failures; tuples and integer-keyed dictionaries as tool results are rejected; empty or
   duplicate call ids are rejected.
