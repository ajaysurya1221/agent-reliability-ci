# REVIEW: S2 LangChain adapter spike

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-10. Author of the spike: Codex Astra 6.
Method: I re-ran `run_spike.py` myself, read `adapter_spike.py` and `FINDINGS.md`, then ran a
four-lens independent review (ARCI semantics, LangChain internals, product API, evidence) in
which every finding was re-checked by a separate skeptic. 15 agents, 11 findings raised, 0
refuted, 4 narrowed. Full output: `S2-review-workflow.json`.

## Verdict: REVISE (mechanics accepted, adapter design changed)

**Accepted as proven.** A `create_agent` agent runs as an ordinary ARCI trial through the
unchanged worker, runner, `ToolBox`, grader and CLI. Tools execute exactly once. All three
faults fire and are read from recorded events. The budget is enforced. `BudgetExceeded` and
`ReplayMiss` keep their outcomes even if a LangChain middleware swallows them, because the
`ToolBox` latches still fire. My re-run: every technical check OK. The single FAIL is the
scope check, caused by files the parallel lanes wrote (`adr-0012-draft.md` and S1's files),
not by S2.

**Not accepted: the adapter design the spike recommends.** Five changes, each confirmed
against the installed LangChain 1.4.9 source and by in-memory probes.

| # | Finding | Why it matters | Required change |
|---|---|---|---|
| 1 | Faults are turned into error `ToolMessage`s by the adapter. Native LangChain does not do that: a tool exception leaves `invoke` unless the user added `ToolRetryMiddleware` or `ToolErrorMiddleware` (`tool_node.py:391-399`, `factory.py:1141-1145`) | The gate would pass an agent that crashes in production and fail one that recovers in production. Found independently by all four lenses | Raise the fault as an exception from the tool-execution position. The ARCI middleware is innermost (last in the list). The user's own error middleware, or its absence, decides the outcome |
| 2 | A message with several tool calls is rejected and scored FAIL/crash | Real models emit parallel calls by default. An adapter limit would count against an arm and could BLOCK a candidate | Serialise by the call's index in the message so order is deterministic. Anything the adapter cannot support is ERROR, never FAIL |
| 3 | The user must write every tool twice (bodies in an ARCI toolset, schemas for LangChain) plus a capture object and an entry function | Contradicts the plan's objective; the gated agent is also not the shipped agent, since LangChain's argument validation is skipped | The adapter derives the toolset from the user's own `BaseTool` objects. No frozen interface blocks this |
| 4 | Tool results reach the model as ARCI canonical JSON; final-answer capture requires string content | A real model would read different observations than in production; list-block content would crash a finished trial | Build message content by LangChain's own rule; keep canonical JSON for recording only. Capture the answer with `message.text` |
| 5 | Replay REPRODUCED never looks at the final answer the oracle grades | Replay would stay green if answer capture broke | Record the final answer as a boundary event and compare it in replay, or state that replay verifies the tool-call sequence only and add a negative test |

**Two corrections to numbers and wording**

- Per-trial cost is about 1.5 s, not 0.75 s: a graded trial starts two processes that each
  import LangChain (worker and grader). The scaffold must keep the check function in a module
  that does not import LangChain.
- A raised tool error reaches any ARCI agent scrubbed to one line with numbers and paths
  replaced (`toolbox.py:298-307`, `fingerprint.py:17-25`). This is existing kernel behaviour,
  equal for both arms. It goes in the recipe as a stated limit.

## What a user writes under the revised design

1. One changed line: pass ARCI's middleware into their existing `create_agent` call.
2. `make_tools(task, seed) -> list[BaseTool]`: their existing tools, fresh per trial.
3. `check(task, final_state) -> bool`.
4. A task file and `arci.yaml`.

This matches the plan's objective. The spike's recommended API did not.

## Consequence

The phase 0 gate for S2 is not passed yet. The revised design was probed in memory by the
reviewers but has no recorded end-to-end evidence. Task S2b proves it with the same rigour:
`plan/exec/v2/tasks/S2b-langchain-adapter-revised.md`.

The original S2 brief asserted the error-`ToolMessage` premise in its question 2, so the
spike inherited that error from my brief. S2b's brief states the native behaviour instead.
