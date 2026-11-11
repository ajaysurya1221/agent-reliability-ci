# TASK S2: LangChain adapter spike (phase 0, no product code)

You are the implementer. The orchestrator re-runs everything you report; your report is not
acceptance evidence. Read `AGENTS.md` first and obey its hard rules.

## Owned files

Only `plan/exec/v2/spikes/s2/`. Create nothing and edit nothing anywhere else. No changes under
`src/`, `tests/`, `docs/` or `examples/`. No git commands that change state. No network. If the
goal seems to need a change under `src/`, stop and say exactly which line and why.

## Environment

A separate interpreter with LangChain already installed:

    /Users/ajay/Developer/.arci-worktrees/v2-spike-venv/bin/python

It has `langchain==1.4.9`, `langgraph==1.2.20`, `langchain-core==1.7.7`, `pydantic`, `pyyaml`.
Import `arci` from this checkout with `PYTHONPATH=src` (plus the spike directory so the worker
child process can import your modules; see `docs/design/0006-cwd-on-the-child-import-path.md`).
Run the CLI as `PYTHONPATH=src <that python> -m arci ...`. Do not install anything.

The installed LangChain source in that environment's `site-packages` is the authority for the
API. Read `langchain/agents/middleware/` (`AgentMiddleware.wrap_tool_call`, `ToolCallRequest`)
and `langchain/agents/factory.py` (`create_agent`) before writing code. Verified signature:
`wrap_tool_call(self, request: ToolCallRequest, handler) -> ToolMessage | Command`.
Fake models live in `langchain_core.language_models.fake_chat_models`.

## Read first in this repository

`src/arci/interfaces.py`, `docs/AGENT_SEMANTICS.md` (trial outcomes, the tool boundary),
`src/arci/worker.py`, `src/arci/toolbox.py`, `src/arci/perturb.py`, `examples/retry_agent/`
(the pattern for agent, toolset, oracle and manifest), `docs/DESCRIPTOR.md`,
`plan/exec/v2/PLAN.md` phase 3.

## Goal

Prove that an agent built with `langchain.agents.create_agent(..., middleware=[...])` can run
as an ordinary ARCI Python-agent trial through the real runner, with every tool call passing
the existing `ToolBox` boundary, using a scripted fake chat model and no network.

## Deliverables (all inside the owned directory)

1. `adapter_spike.py` containing:
   - a middleware class whose `wrap_tool_call` sends each tool call through
     `ToolBox.call(name, **args)` so recording, budgets and the built-in faults apply;
   - a toolset factory `(task, seed) -> toolset` with `.tools` and `.snapshot()`; the snapshot
     returns the environment state plus the agent's captured final output;
   - agent functions `baseline(task, tools, rng) -> dict` and `candidate(...)` that build the
     LangChain agent with a scripted fake chat model and invoke it synchronously. The baseline
     script retries a failed tool call once; the candidate does not;
   - an oracle `(task, final_state) -> bool` that reads only the snapshot.
2. A v1 experiment (`arci.yaml` or manifest JSON) with a small `n_per_arm` and one condition
   each for `tool_timeout`, `tool_error_once` and `empty_result`.
3. `run_spike.py`: runs everything below into `plan/exec/v2/spikes/s2/out/` and exits
   non-zero if any check fails. It prints one line per check: `OK` or `FAIL` with the reason.
4. `FINDINGS.md`: results, the recommended product API (exactly what one line a user changes
   and what else they must supply), the LangChain types and modes the adapter must reject,
   measured per-trial start cost, and open risks.

## Questions the spike must answer with evidence

1. **Exactly-once execution.** `ToolBox.call` itself invokes `toolset.tools[name]`. So either
   the middleware does not call `handler` and builds the `ToolMessage` from the `ToolBox`
   result, or the toolset's tool delegates to `handler`. Pick one, show the tool body runs
   exactly once per call (count it), and explain the choice.
2. **Fault visibility.** An injected `ToolFault` must reach the agent the way a real tool
   failure does in LangChain (a `ToolMessage` with error status the model can react to), so a
   robust agent recovers and a fragile one fails. `BudgetExceeded` and `ReplayMiss` must end
   the trial with the outcomes `docs/AGENT_SEMANTICS.md` requires. Show each.
3. **Each fault fires.** For each of the three conditions, show from the recorded events that
   the fault was injected at least once.
4. **Budget.** A run with a tiny tool-call budget ends as FAIL with termination `budget`.
5. **Final state.** The oracle's verdict depends on the agent's final answer captured through
   `snapshot()`, not on the agent function's return value.
6. **Replay.** `arci bundle` then `arci replay` on one failing trial returns REPRODUCED.
   `arci diff` between one passing and one failing trial of the same pair reports the first
   divergence.
7. **Parallel tool calls.** Script one model message that requests two tool calls at once.
   Record what LangChain does. Implement either a deterministic serial order or a clear
   rejection, and justify it against `toolbox.py` (no locks; replay consumes calls in order).
8. **Unsupported shapes.** Show a clear error, not silent pass-through, for a tool that
   returns a `Command`, for non-JSON arguments or results, and for an async invocation.
9. **Cost of a trial.** Measure the child-process import and start time with LangChain
   loaded, median of 10.

## Pass conditions

1. `run_spike.py` exits 0 with every check `OK`, run twice in a row with identical verdicts.
2. `shasum -a 256 -c FROZEN.sha256` still passes, and `git status --short` shows changes only
   under the owned directory.
3. `.venv/bin/ruff format --check` and `.venv/bin/ruff check` are clean on the owned directory.

A failed check is a valid result. Report it plainly with the evidence.

## Final message

Files created, the exact commands you ran with their last lines, the answer to each of the
nine questions in one or two lines, anything you could not do, and risks. No long logs.
