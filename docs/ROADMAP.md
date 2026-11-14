# Roadmap

v0.1 proved one thing: a measured regression becomes an executable, reduced failure case, for
Python agents. v0.2 extends that to any program that speaks MCP over stdio. v0.5 adds System One
decisions made by command agents, and v0.6 makes the documented Jev workflow ready for day one, and
v0.7.0 runs it against Jev and publishes an intent-routing calibration audit, and v0.8.0 ships
the onboarding path (PyPI, `arci demo`, `arci.yaml` and `arci init`) whose target, a first
experiment in ten minutes, is measured by `docs/measurement/ttfv-protocol.md` and not yet
established by cold-reader receipts. v1.0.0 adds `trace-check` and `triage`. v2.0.0 adds
multi-task suites with a sequential decision rule and the LangChain adapter, and v2.1.0 adds
tool outcomes in suite reports and a clean model swap in the quickstart.

## Done in v0.2

The out-of-process boundary: command agents (any subprocess) behind a harness-owned stdio MCP
boundary, with record, replay, budgets and fault injection; a bridge that serves any python toolset
as an MCP server; a real local-LLM example. See docs/REAL_AGENTS.md and
docs/design/0002-out-of-process-boundary.md.

## Done in v0.3 and v0.4

`interval_method: newcombe`, and pre-registered `looks` with equal Bonferroni spending.
For v1 experiments, alpha-spending functions or confidence sequences are not planned unless the
Bonferroni cost proves too high in practice; v2.0.0 suites use a separate sequential rule (see
below).

## Done in v0.5

The command-agent boundary also serves `POST /v1/systemone`, keeps the real TypeSafe key out of the
agent, and records, perturbs, minimises and replays decisions. It supports seeded fixtures for CI
and a real Jev upstream. See docs/DECISIONS.md and docs/design/0003-decision-boundary.md.

## Done in v0.6

Day-one readiness: gateway path prefixes, tolerant vendor-shaped responses, preflight receipts,
parent-paced live runs, token/cost reporting, raw upstream snapshots, a pinned JavaScript SDK agent,
and release/write-up guidance. These behaviours were initially fixture-tested from vendor
documentation.

## Done in v0.7.0

The pre-registered day one ran against the direct Jev endpoint on 2026-10-03; see
[the committed results](results/jev/README.md). A pre-registered intent-routing calibration audit of
the decision model is published in [results/jev-calibration](results/jev-calibration/README.md)
(protocol: `bench/jev_calibration/PROTOCOL.md`). The gateway route, provider rate limits under load
and billed spend remain unverified.

## Done in v0.8.0

The onboarding release: the PyPI package and `uvx --from agent-reliability-ci arci demo`, the
`arci.yaml` descriptor with its generated JSON Schema, `arci init`, the smoke-design notice, the
current directory on the child import path, the CI install matrix and release workflow, the
measurement protocol, and the README's first screen. Also released: `arci plan`, opt-in
`arci report --pass-k` and the platform-portability fixes that had been on `main` since v0.7.0.
See [CHANGELOG.md](../CHANGELOG.md).

## Done in v1.0.0

`arci trace-check` compares selected recorded views across compatible native
stores. `arci triage` selects representative paired candidate failures from one
native store and shows containing-event/tool context without manual JSONL
inspection. Triage retains the complete statistical gate and its exit code;
trace drift does not redefine success or replay. See the [triage recipe](recipes/triage.md)
and [cross-run comparison recipe](recipes/trace-check.md).

Both commands are new in v1.0.0; v0.8.0 does not contain them. Independent agent
QA is distinct from human adoption and retention, which remain unmeasured.
Importers and snapshot-update workflows remain proposals.

## Done in v2.0.0

Suite experiments (`arci-suite/1`): a grid of tasks by fault conditions, run in balanced
rounds, decided by two one-sided betting tests in exact arithmetic
([STATISTICS_SUITE.md](STATISTICS_SUITE.md), design record 0011). The LangChain
`create_agent` adapter behind the optional extra `agent-reliability-ci[langchain]`, with
`arci init --langchain` and the [LangChain recipe](recipes/langchain.md) (design record
0012). Fault accounting in reports, `arci report --format html`, an optional pull-request
comment from the Action, and an exact calibration bench for the suite rule. One pre-registered
study on two local models, which ended in BLOCK at round 1 (run 1 of the order-desk study).
Every v1 record, command and exit code is unchanged. See [CHANGELOG.md](../CHANGELOG.md) and design record
0013.

## Done in v2.1.0

Tool outcomes in suite reports. A model comparison in the quickstart that changes only the
model ([model-swap recipe](recipes/model-swap.md)). The second pre-registered run of the
order-desk study, and a write-up of both runs with the correction to run 1's first write-up
([results/order-desk-study.md](results/order-desk-study.md)). See design record 0014.

## Next

Nothing is scheduled. From v2.1.0 on, an item is taken up only when someone who would use it
asks for it, or when a recorded run shows the need.

Design record 0014 lists what is not in 2.1.0: interrupts and human-in-the-loop steps (one
reader asked; the adapter still rejects them), async agents, compound fault conditions,
stronger bets near the margin, and every item design record 0013 lists as not built for
suites (`minimize`, `bundle`, `replay` and `trace-check` for suite stores, JUnit for suites,
tools with injected arguments, MCP clients other than ARCI's own revision, and command-agent
suites beyond what the schema already allows, which are untested end to end). There is one
framework adapter, for LangChain.

On compound fault conditions: a condition can already list several faults (`faults:` in
`arci.yaml`, applied together in order), in v1 and in suites. What 2.1.0 does not have is a
suite example or a study that registers one; the quickstart's conditions hold at most one
fault each.

## Earlier candidates (last revised for v0.8.0, October 2026; none is scheduled)

1. **Per-request pacing through parent IPC**, replacing the documented divide-by-k trial-start
   approximation for agents that make several decisions per trial.
2. **Counterfactual replay of recorded decisions**, if agent-path dependence can be represented
   without overstating what a re-perturbed recording proves.
3. **Extend the published intent-routing calibration audit** to labelled coding-agent permission
   decisions, with a separate protocol and explicit limits.
4. **System One emulator over a local model via `system-one-adapter`**.
5. **Streamable HTTP transport** and several MCP servers per trial.
6. **Importers**, split into analysis-only and replay-capable, built only from authentic versioned
   fixtures: OTLP GenAI spans, Claude Code `stream-json`, Codex `--json`.
7. **Cohort localisation** (spectrum-based scoring of step signatures across all passing and
   failing trials), and minimisation of injected context and recorded history.
8. **Task-clustered aggregation** across many tasks (average within task, then within family).
   v2.0.0 suites took a different route: balanced rounds over a grid of tasks by conditions.
9. SQLite index and resumable runs, and a growing perturbation library (reordered results,
   misleading tool output, latency, crash-after-checkpoint). The HTML report on this list
   shipped in v2.0.0.

## Known limits of v0.1

The limits of the current release are in the README section "What it does not do" and in
design records 0013 and 0014. The four below have held since v0.1.

- The tool boundary only sees what goes through it. An agent that touches the filesystem or the
  network directly is outside the contract; a fresh working directory is not a sandbox.
- Deterministic replay is guaranteed for seeded, fixture-backed agents. A live model is not
  replayable token for token; what replays is the tool boundary.
- Hashes are integrity checks, not signatures.
- Trace divergence shows where two runs part ways. It is evidence for a cause, not proof of one.
