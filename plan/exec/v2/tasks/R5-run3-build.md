# R5: build the study folder for run 3 (order-desk, message at the empty lookup)

Plan (approved by the maintainer on 16 Nov 2026): `plan/exec/v2/study/PLAN-run-3.md`. Read it
first. This task builds the code for the run. It runs no model and starts no trial with a
real model.

## Rules

- Work only inside `plan/exec/v2/study/order-desk-empty-message/` (new). Change nothing else.
- No git command that changes state. No network. Install nothing. Do not call `uv`.
- Do not start Ollama and do not call a real model. Offline runs with the scripted model
  are allowed and wanted.
- Python and tools to use (read and execute only; you cannot write there):
  `/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/run3-env/bin/python`
  and `.../run3-env/bin/arci` (ARCI 2.4.0, langchain 1.4.10, langchain-core 1.7.7,
  langgraph 1.2.20, langchain-ollama 1.1.0). Run pytest as
  `PYTHONDONTWRITEBYTECODE=1 <python> -m pytest -p no:cacheprovider ...` (pytest may not be
  installed there; if not, write the tests so that `<python> tests/test_x.py` runs them
  with plain asserts and a `main()` that calls every `test_` function, and say so).
- Any offline `arci run` writes its output under a folder you create inside
  `order-desk-empty-message/_offline/` and delete nothing afterwards; say what is there.

## Interface (fixed; a second agent writes tests from this section without reading your code)

In `order-desk-empty-message/agent.py`:

- `EMPTY_LOOKUP_TEXT: str`, exactly:
  `lookup_order returned an empty result. Call lookup_order again with the same order_id.`
- `class ExplainEmptyLookup(AgentMiddleware)` with `wrap_tool_call(self, request, handler)`:
  it calls `handler(request)` exactly once and returns its result unchanged, except in one
  case. The case: `request.tool_call["name"] == "lookup_order"` and the result is a
  `ToolMessage` whose status is not `"error"` and whose content is the text `null`
  (compare `str(content).strip() == "null"`). Then it returns a new `ToolMessage` with
  `content=EMPTY_LOOKUP_TEXT` and the same `tool_call_id`, `name` and `status` as the
  result. It never calls the handler a second time, never raises for a result it does not
  recognise, and does nothing for other tools, for error results, or for a lookup that
  returned an order.
- Audit, supporting evidence only: if the environment variable
  `ORDER_DESK_EMPTY_TEXT_AUDIT` names a file, each replacement appends one JSON line
  `{"tool": "lookup_order", "tool_call_id": "<id>"}` to it. If the variable is unset, or
  the write fails, the middleware behaves the same and writes nothing. The audit must not
  change what the model receives.
- `settings(candidate: bool)`: the middleware list is `[retry, ReturnToolErrors()]` for the
  candidate arm, exactly as in run 2, and `[retry, ReturnToolErrors(), ExplainEmptyLookup()]`
  for the baseline arm. Nothing else differs between the arms. The system prompt, the
  retry settings, `ReturnToolErrors`, `fault_exceptions`, and everything below `settings`
  stay as in `order-desk-recoverable/agent.py`, character for character. Change the
  module docstring and add the new class and constant; that is all.

## Deliverables

1. `order-desk-empty-message/` with `tools.py`, `check.py`, `configuration.py`,
   `offline_model.py`, `register.py` copied byte for byte from
   `plan/exec/v2/study/order-desk-recoverable/`; `agent.py` as specified; `tasks.jsonl` with
   exactly the 8 lines of run 2's `tasks.jsonl` whose `action` is `stock_note`, in the same
   order (their `quickstart_settings` are rewritten by `register.py`, see 3).
2. `arci.yaml`, with this content (register.py will re-dump it; the values must survive):

   ```yaml
   suite_id: order-desk-qwen3.5-4b-empty-lookup-text
   tasks: tasks.jsonl
   toolset: agent:toolset
   oracle: check:check
   baseline:
     label: with-empty-lookup-text
     agent: agent:baseline
     candidate_id: ollama:qwen3.5:4b-mlx-ctx32k+empty-lookup-text
   candidate:
     label: run-2-setup
     agent: agent:candidate
     candidate_id: ollama:qwen3.5:4b-mlx-ctx32k
   conditions:
   - id: empty_result
     faults:
     - name: empty_result
       tool: lookup_order
       occurrence: 0
   rule:
     alpha: 1/20
     delta: 1/10
     stakes:
     - 1/4
     - 1/2
     max_rounds: 40
     max_errored_pairs: 4
     scenario_seeds: per_round
   budgets:
     max_tool_calls: 12
     max_model_steps: 12
     max_seconds: 120
     grader_seconds: 20
   prior_runs:
   - order-desk-gemma4-12b-vs-qwen3.5-4b@533c6d1a78ccc1a201eb7e265a61873244d48c2ac0e26cde5a50bc7dfd5f83bb
   - order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@eaa438b195f418b66878a57422ab6229b2171c74dd8d6eb7ba097ec4a09b96fb
   ```

   If the released tool refuses any key (check with `arci plan arci.yaml --help` and a
   plain `arci plan` on it), stop and report the exact message; do not drop a key silently.
3. Run `register.py` once with
   `ARCI_QUICKSTART_BASELINE='ollama:qwen3.5:4b-mlx-ctx32k'`,
   `ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'`,
   `ARCI_QUICKSTART_TEMPERATURE=0.7` (it calls no model) and show that the rule, the arms,
   the condition and `prior_runs` are unchanged in meaning afterwards.
4. `tests/test_middleware.py`: model-free tests of `ExplainEmptyLookup` with a fake request
   and handler: the null lookup is replaced; a lookup that returned an order, another tool
   returning the text `null`, an error-status result and a non-`ToolMessage` result pass
   through untouched (same object); the handler is called exactly once in every case; the
   audit line is written when the variable is set and nothing is written when it is not;
   the baseline arm's middleware list ends with `ExplainEmptyLookup` and the candidate
   arm's list has none (build `settings()` with the offline environment, no model call).
5. The end-to-end proof that the replacement really happens through ARCI's adapter and its
   injected `empty_result` fault, with no real model. This is the most important item: if
   the middleware never sees the text `null`, both arms are the same program and the run
   would be worthless. Use whatever is the most direct honest way, for example a scripted
   chat model driven through `make_adapter` with the fault active, or an offline
   `arci run` of a copy of the descriptor with the offline model, with
   `ORDER_DESK_EMPTY_TEXT_AUDIT` set. Show: (a) in the baseline arm the message the model
   receives after the injected empty lookup is `EMPTY_LOOKUP_TEXT`; (b) in the candidate arm
   it is the text `null`; (c) the store still records the injected fault in both arms;
   (d) the audit has one line per baseline trial in which the fault fired and none for the
   candidate arm. If the offline scripted model cannot show (a) and (b) because it does not
   expose what it received, write a small scripted chat model for the test that records the
   messages it is given. Put this in `tests/test_end_to_end.py`.
6. `tests/code_retry_demo.py` and `tests/test_code_retry_demo.py`: a middleware
   `RetryEmptyLookupOnce` that, for the same case, calls `handler(request)` once more and
   returns that second result; and a model-free end-to-end test that shows an injected
   empty lookup is followed by exactly one more recorded `lookup_order` call with no model
   step between them, and that the model then receives the order. This middleware is NOT
   used by the run and must not be imported by `agent.py`. It exists to show a reader how a
   code retry behaves.

## Acceptance

- `diff -r` of the new folder against `order-desk-recoverable/` shows only: `agent.py`
  (the additions above), `arci.yaml`, `tasks.jsonl`, and the new `tests/` and `_offline/`.
- `arci plan arci.yaml` (run inside the folder with the three environment variables set)
  prints a plan and exits 0.
- All tests pass with the environment above. Paste the last lines.
- Report: files created, the diff of `agent.py` against run 2's, each command and its last
  lines, what you could not do, and any doubt about whether the model really receives the
  message. Short. No long logs.
