# Trust model (v0.1)

FROZEN. Be exact about what this tool defends against, because a testing tool that overstates its
guarantees is worse than none.

## What is trusted

- The harness, the manifest author, the toolset (environment) and the oracle.
- The agent under test is **the user's own code**. It is assumed buggy, flaky, slow, crash-prone
  and careless. It is NOT assumed hostile.

## What v0.1 guarantees against a buggy agent

None of the following may change a verdict in the agent's favour, and none may be reported as an
ordinary agent failure when the fault is the harness's or the grader's:

- crashing, hanging, exiting non-zero (even after finishing), leaving descendants behind in the
  worker's process group (a descendant that starts its own session is outside the cleanup
  guarantee);
- swallowing any exception the tool boundary raises (`ToolFault`, `BudgetExceeded`, `ReplayMiss`,
  a broken injector);
- claiming success it did not earn (success comes only from the independent oracle);
- mutating values the boundary returned to it;
- printing to stdout or writing junk bytes onto the protocol channel;
- passing values that are not JSON (NaN, unencodable text) across the boundary;
- a broken environment factory; a broken, slow, hanging or non-boolean oracle; a broken or
  malformed fault injector; a failing event sink.

Fault classification survives what the agent does next: a harness fault or a blown budget is
reported to the parent the moment it happens, so hanging or exiting afterwards cannot turn it into
an ordinary timeout or crash.

## Command agents (v0.2)

For a command agent the environment, the recorder, fault injection, budgets and the fault latches
live in a harness-owned boundary process. The agent's process tree contains only a byte-relay shim.
A buggy agent can no longer corrupt the record by accident, whatever it does in its own process.
This is isolation from accident, not a sandbox: the agent can still reach the unix socket it was
given, and anything it does outside MCP (files, network) is invisible.

## What v0.1 does NOT guarantee

The agent, the tool boundary and the environment run in the same child process. A deliberately
hostile agent can reach into that process (forge protocol lines, touch the environment object
directly, patch the ToolBox). v0.1 adds cheap obstacles (a per-trial protocol nonce, exit-status
checks, private state) but makes no security claim. Closing this properly means moving the
environment and the recorder out of the agent's process behind an RPC boundary: that is the v0.2
tool gateway / MCP proxy (docs/ROADMAP.md).

Also outside the boundary: anything the agent does without going through the ToolBox (files,
network, subprocesses). A fresh working directory is not a sandbox. Contracts that ask for
unobservable invariants are rejected rather than silently ignored.

## Bundles

A replay bundle embeds code. Replaying a bundle executes that code. Hashes prove the payload matches
what the bundle declares; they do not prove who made it. Replay bundles only from sources you trust.
A bundle embeds only the files you explicitly include (the minimiser's output embeds none), so
portable replay needs every referenced module, fixture and a compatible environment. Replay also
requires the recording to be consumed exactly; anything else is INVALID.
Payload paths are confined to the bundle's temp directory; absolute paths and `..` are rejected.

## Decisions (v0.5)

A command agent may call a System One decision endpoint (TypeSafe's Jev API) through a
harness-owned loopback endpoint. What that adds, and what it does not:

- Only supported, serial calls that reach the injected `TYPESAFE_BASE_URL` are observed. An agent
  that hard-codes the provider's URL, or an SDK that ignores the environment, bypasses the boundary
  and is invisible, exactly like direct network access.
- The real API key stays in the harness and the boundary. The agent receives a per-trial token that
  is unrelated to the protocol nonce and is never recorded.
- Every admitted request (state and extra fields included) and every response (status, body and
  the `retry-after` header) is recorded in the trial and in any bundle made from it. Records may
  therefore contain sensitive state. Adversarial content in the state is the agent's problem.
- Each attempt consumes both the tool-call and the decision budget; exhaustion is FAIL/budget.
- Real provider or fixture faults (network, 401/403, 429, 5xx, a malformed or mis-typed answer,
  a fixture that raises) are harness faults: ERROR, never an agent failure. Injected faults are not.
- A local rejection (wrong token, oversize or malformed request) is served deterministically and
  sets no latch; the oracle still decides the trial.
- Replay executes no upstream, no fixture and no perturbation, and requires exact ordered
  consumption; a parent-verified miss or leftover is ERROR/replay_miss and the replay is INVALID.
- Confidence reported by a decision model is not certified accuracy. The oracle and the gate are
  unchanged; nothing a decision model says enters a verdict except through the agent's actions.
- Determinism and minimality claims hold for seeded fixtures. Live Jev is sampled; what replays
  is the recording.
