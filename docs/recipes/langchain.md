# Gate a LangChain tool-retry change

Use `arci.adapters.langchain.make_adapter` for synchronous LangChain `create_agent` agents
whose tools you can replace with an isolated environment and whose success you can grade from
state. The runnable [order desk](../../examples/langchain_quickstart/README.md) starts offline:
24 tasks × four conditions, default suite rule, a planted candidate regression, **BLOCK at
round one**. No model server or API key is needed. Its five-step README is the executable path;
`tests/unit/examples/test_langchain_quickstart.py` runs it in a copied directory through the CLI.

## Read the adapter file

Open [agent.py](../../examples/langchain_quickstart/agent.py). Its statements, in order:

1. `os` reads configuration; `Any` describes the framework's heterogeneous settings mapping.
   `ToolRetryMiddleware` and `init_chat_model` are public LangChain APIs. `OfflineModel` and
   `make_tools` are the user's local files; `make_adapter` is the ARCI boundary.
2. `settings(candidate)` chooses `ARCI_QUICKSTART_BASELINE` or `ARCI_QUICKSTART_CANDIDATE`.
   Each is a `provider:model` identifier. The shared `inference` mapping fixes temperature
   at 0; for Ollama it disables reasoning. Other providers retain their own default reasoning
   mode. Use matching provider settings for the two arms. An absent variable constructs the
   scripted offline model. No provider is contacted at module import.
3. `ToolRetryMiddleware` grants the baseline one retry and the candidate none, with zero
   delay and no jitter. It handles `TimeoutError` and `RuntimeError`, returning a tool-error
   message when attempts run out. The fake candidate abandons that error; the baseline never
   sees it after a successful retry. This is the intentionally planted behavioural difference.
4. The returned dictionary contains `model`, `middleware` and `system_prompt`: ordinary
   `create_agent` settings, with the same instructions for both arms. The two small settings
   functions select the arm. They are called afresh inside the trial worker.
5. `make_adapter(make_tools, baseline_settings, candidate_settings, fault_exceptions=...)`
   returns `toolset`, `baseline`, `candidate`, referenced by the descriptor. Fault mappings
   use kinds `timeout` and `error`, not names `tool_timeout` or `tool_error_once`. The factory
   receives task and seed; the default input conversion requires a string `task['input']`.
   Supply `task_to_input` only for a different graph input shape.

Model-client retry settings govern provider retries. `ToolRetryMiddleware` governs tool attempts
inside the recorded boundary. Do not treat a provider outage as evidence of a weak agent.

## Snapshot and checker contract

`make_tools(task, seed)` returns `ToolEnv(tools, snapshot=...)`. The environment is fresh for each
trial; seeded price, SKU and stock prevent a script from hard-coding the right refund or stock
note. Tool names and schemas must be seed-independent. The factory may be called at seed zero
during replay, so constructing it must be safe without running tool bodies.

The adapter passes the checker this shape:

```python
{
    "final_output": "agent's last text or None",
    "structured_response": None,  # or JSON-compatible structured output
    "state": {"order_id": "...", "order": {...}, "stock": 12},
}
```

`state` is exactly the dictionary returned by `ToolEnv.snapshot`. Without a snapshot callback
it is `None`. [check.py](../../examples/langchain_quickstart/check.py) imports no agent framework:
it requires the requested order, the correct refund amount and exactly the requested notes.
It ignores claimed success. Snapshot values must be JSON-compatible; the checker must return
an actual boolean. An oracle exception is ERROR, never agent FAIL. A real system should grade
its own independently observable effects instead of trusting a self-reported answer.

Clean tasks use two or three tool calls. All four conditions target the first `lookup_order`:
clean leaves it alone; timeout/error prevent its execution once; empty_result replaces its
returned value with null. Both scripts retry an empty read; only the baseline retries errors.
Retries of writes require idempotency in your real tool; this example's refund and note are
idempotent too. A tool fault that never reaches its selected tool never fires.

## Failure classification

The table describes **trial outcomes**. A suite tolerates its registered number of errored pairs
and scores each conservatively in both wealths. Above that limit the suite verdict is ERROR.
An individual ERROR therefore does not invariably imply a suite ERROR; v1 experiments treat
any ERROR as invalid. Candidate hard invariants can force BLOCK independently of rates.

| Source | Outcome and reason |
|---|---|
| Checker returns false, missing success state, or wrong business state | FAIL; answer text cannot rescue it. |
| Injected timeout/error or real tool exception | Recoverable by policy/middleware. If uncaught, FAIL/crash; live exceptions keep their original type and attributes. A tool-side timeout is not automatically provider infrastructure. |
| Empty injected result | Ordinary JSON null; checker determines success after the policy handles it. |
| Invalid tool arguments, unknown tool, non-finite arguments | Agent-side error; FAIL if not recovered or if the final state is wrong. |
| Model exception after model invocation, without an infrastructure signature | FAIL/crash unless handled by supported policy. |
| Model/tool budget exhausted, trial timeout | FAIL/budget or FAIL/timeout; middleware cannot swallow terminal boundary failures. |
| Tool factory, settings callable, `create_agent`, input conversion or graph input rejection before the first model call | ERROR/harness_error: configuration failure is not a tied pair of agent failures. |
| Provider HTTP 401, 403, 407, 408, 429 or 5xx; connection/transport timeout, DNS or TLS failure | ERROR/harness_error. Detection includes binding/output processing inside the model handler. |
| Missing/incompatible framework APIs or mismatched adapter toolset | ERROR/harness_error. Without the extra, `init --langchain` gives the install hint and exits 3. |
| Unsupported tool/graph/middleware feature, non-JSON tool result, invalid tool-call ids, non-AI model response, interrupt or tool-order deadlock | ERROR/harness_error; the adapter cannot faithfully record it. |
| Oracle/loader/snapshot failure | ERROR (grader_error or harness_error according to the failing boundary), never agent failure. |
| Replay call mismatch, missing or unconsumed recording, invalid bundle seal | Invalid replay / ERROR, never a silent live call. |
| Replay exception class/diagnostic cannot be reconstructed | ERROR/harness_error, not proof that the policy changed. |

## Supported surface and rejected features

The settings whitelist is `model`, `system_prompt`, `middleware`, `response_format`, `name`.
Checkpointing, stores, context/custom state, async-only invocation and interrupted graphs are
outside this adapter's contract. Tools with artifacts, `return_direct`, built-in error swallowing
(`handle_tool_error`, `handle_validation_error`), injected runtime/config/callback arguments,
reserved `tool`/`self` arguments or `Command` results are rejected because the boundary cannot
record their full semantics. Middleware-owned tools are rejected. Callable structured-output
error handlers are rejected. Duplicate tool names and empty/missing/duplicate call ids are
rejected because there is no unambiguous recorded call identity. Tuples, integer-keyed result
dictionaries, non-finite/non-JSON results and invalid structured output are not JSON snapshots.

Validation executes twice on the same raw input, so validators with side effects are unsupported.
`functools.partial` functions are accepted here although native `create_agent` in the supported
LangChain version rejects them. `BaseTool.run` supplies run managers; parent callback linkage can
differ. Parallel calls from one response are serialized in declared order, including retry
backoff. A waiting call gets a deadlock error after 30 seconds with no active call; the overall
trial budget still bounds an active call.

Middleware is trusted code: replacing the request's tool or returning without its handler can
bypass recording. Direct side effects outside the tool boundary are unobserved. This adapter is
not a sandbox. These limitations apply equally to a real model and the offline fake.

## Replay limits

Suite `bundle` and `replay` commands currently exit 3 as unsupported. Do not interpret `arci gate`
as re-executing the agent: it recomputes the suite decision from saved records. For a v1 trial
bundle, the adapter rebuilds schemas at seed zero and reads recorded tool results without
executing tool bodies. It does not record/replay live model inference; replay may need a model
connection unless the model itself is scripted or otherwise replayable. Different policy paths
can still reproduce when the compared sequence, outcome and fingerprint agree.

Live exceptions are re-raised unchanged. Replay reconstructs only exception class and a
round-trippable scrubbed diagnostic, not original messages or attributes. `error_types` supplies
custom classes and overrides builtin names. The reconstructed diagnostic must match exactly;
unrecoverable text (including scrubbed non-literal `KeyError` keys) produces a harness ERROR.
Real `error` diagnostics are reconstructed regardless of fault tag unless detail equals
`injected error`. Custom perturbations must preserve real kind/detail and use that exact text
for synthetic errors; changed diagnostics or synthetic class-like text can cause divergence.

## Cost and interpretation

Each clean trial uses two or three tool attempts and three or four model calls. An empty lookup
adds one model call and one tool attempt. The baseline's exception retry adds a tool attempt
inside the middleware without an extra model call. The registered per-trial limits are six of
each and 15 seconds. There are 192 trials per complete round and at most 960 over the default
five rounds. Offline provider cost is zero; real inference cost is the sum of model input/output
tokens at your provider's rates, or local compute time. There is no dollar estimate or inference
recording in this example. Choose slower-local-model budgets before the experiment, not after
seeing a result.

The offline cell laws are degenerate: 48 pairs tie and 48 favour baseline, for every seed.
The test enumerates them with `suite_stats.operating_characteristics` and obtains P(BLOCK)=1
at round one. That is a fixture claim. Real-model outcomes, independence and stationarity have
not been measured. PASS would describe relative performance over the registered suite within
the margin, not absolute reliability or unseen tasks. INCONCLUSIVE is unresolved evidence.
Prior-run bookkeeping does not reset the statistical error budget or permit repeated campaigns
until PASS. See [the suite statistics contract](../STATISTICS_SUITE.md).

LangChain brings `langsmith` transitively. ARCI does not enable tracing; existing environment
variables can enable outgoing traces. Set both `LANGSMITH_TRACING=false` and
`LANGSMITH_TRACING_V2=false` for offline execution; V2 overrides inherited legacy settings.
Run stores can contain sensitive task data even with tracing disabled
([ADR 0012](../design/0012-optional-framework-extras.md)).
