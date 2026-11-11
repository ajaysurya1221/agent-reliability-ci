# REVIEW: S2b revised LangChain adapter spike

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-10. Author of the spike: Codex Astra 6.
Method: I re-ran `run_spike.py` myself (17 OK, 1 FAIL, identical to Codex's runs), read the
user-facing files and `FINDINGS.md`, then ran a three-lens independent review (concurrency,
outcome attribution, evidence and user burden) with a separate skeptic per finding.
12 agents, 9 findings, 0 refuted, 4 narrowed. Full output: `S2b-review-workflow.json`.

## Verdict: phase 0 gate for the adapter PASSES; the prototype design does not ship

**Feasibility is established.** With no change under `src/`, a `create_agent` agent using the
user's own `BaseTool` objects runs under ARCI's boundary. Faults surface as exceptions, so
the user's retry or error middleware decides the outcome. Two calls in one message run in
index order on the success path (reviewers removed the turnstile in memory and the order
flipped in 5 of 20 runs, so the check discriminates). Tool results reach the model
byte-identical to native for strings and dicts.

**The one failed check was my requirement, and it was wrong.** I asked that an injected fault
match a native failure in tool-body counts and exception type. An injected fault skips the
body by the frozen contract (`interfaces.py:122-123`, `toolbox.py:274-286`) and raises
`ToolFault`. The attribution lens confirmed this reading. Parity that holds: no error
handling gives no answer and FAIL/crash; retry middleware gives the right answer with two
recorded calls; error middleware gives the same answer and observation as native.

**Honest count:** 15 checks OK, 2 known limits demonstrated (replay does not verify the final
answer; unsupported modes in replay end as FAIL), 1 FAIL caused by the brief.

## Binding requirements for phase 3

The prototype has two ARCI middlewares that the user must splice their own between. Nothing
enforces that, and both natural mistakes fail silently or hang. The product uses a different
shape, probed in memory by two reviewers and to be proven by phase 3's tests:

**One ARCI middleware, placed first, plus proxy tools.** The adapter hands LangChain a proxy
for each user tool (through the public `ToolCallRequest.override`); the proxy's body calls
`ToolBox.call`, which runs the user's real tool. LangChain's own tool node then validates
arguments, formats results, answers unknown tool names and runs the user's middleware in its
native position. This removes the second middleware, both private-API imports, the hand-built
validation error and the splice.

| # | Requirement | Source finding |
|---|---|---|
| 1 | The adapter owns middleware composition. The rule a user sees is "ARCI's middleware goes first" and a misplacement is a harness ERROR with a fixed message, never a hang | Placement unenforced; retry outside the turnstile deadlocks every retried call |
| 2 | The serial turnstile has an abort flag, a wait timeout that becomes a harness ERROR, and re-entry detection. After a fatal exception in one call of a multi-call message, no later call reaches `ToolBox` | A fatal exception mid-message made the trace nondeterministic and could deadlock |
| 3 | Budget exhaustion and adapter rejections cannot be caught or retried by user middleware (a `BaseException` carrier, converted back outside the user chain) | `BudgetExceeded` was retried with full backoff |
| 4 | A real tool failure reaches user middleware as the original exception object. An injected fault raises `ToolFault` by default, and the user may map a fault kind to an exception class. The same rule applies in replay; a recorded real failure whose type cannot be rebuilt ends as ERROR | Type-filtered retry policies diverged from the deployed agent even with no fault injected |
| 5 | No private LangChain imports. An import-time capability check ends as ERROR. Tests run at both ends of the allowed `langchain-core` and `langgraph-prebuilt` ranges, which the `langchain>=1.4,<2` pin bounds only indirectly | Private formatter and unexported exception spanned three separately versioned packages |
| 6 | In-body rejections derive from `BaseException` so the existing harness latch fires at once. `ToolBox.reject_unsupported(detail)` is added (unfrozen `toolbox.py`) for async detection and for every rejection in replay | Unsupported shapes were recorded as agent-visible tool failures |
| 7 | A mis-named tool call is answered natively and graded as agent behaviour. `response_format` is either captured in the snapshot or named as rejected in the recipe; decided in the phase 3 brief | Recoverable model behaviour ended as harness ERROR |
| 8 | A task-to-input hook: the user says how a task becomes the agent's input | The prototype hard-coded `json.dumps(task)` |
| 9 | Product tests cover every reject reason, list-of-strings results, real-error text and type under a typed retry policy, non-zero retry backoff with three or more calls, and 1,000 repetitions of a failure at index 0 and mid-message with more calls than pool threads | Check coverage gaps |

## Corrections to the plan

- **Objective wording.** "One changed line of agent code" is not true. A user writes a small
  adapter module (44 lines in the prototype, including test instrumentation): a tool factory,
  one builder per arm, one glue line; plus a check function and `arci.yaml`. The plan and the
  launch claim say "a small adapter file", not "one line".
- **Cost.** About 1 second of fixed overhead per trial on an idle machine; budget 1.5 seconds.
  5.6 seconds was seen under load. No speed-up over S2 is claimed.
- **Serialisation changes timing.** Retry backoff that is concurrent natively becomes
  sequential, so wall-clock budgets need headroom for multi-call messages. Stated in the
  recipe as a measured-time limit.
- **Limits that remain in v2.0 and are stated in the recipe:** replay verifies the tool-call
  sequence, not the final answer; `make_tools` must be safe to call again with seed 0 in
  replay; a raised tool error's text is scrubbed in ARCI's records (the model now sees the
  original under requirement 4).

## Fallback

If the proxy-tool shape fails its phase 3 tests, the fallback is the S2b shape with
requirement 1 implemented as an adapter-owned helper that assembles the list.
