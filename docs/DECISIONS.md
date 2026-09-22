# Testing agents that use Jev

A decision is one admitted `POST /v1/systemone` request from a command agent. ARCI serves that
endpoint on loopback, records the request and response as a tool call named
`decision:systemone`, and applies the trial's shared tool-call budget, perturbations, replay, diff,
minimisation and bundle machinery.

## Pointing an agent at the boundary

For each trial ARCI sets `TYPESAFE_BASE_URL` to its loopback listener and `TYPESAFE_API_KEY` to a
random per-trial token. These values are set after `CommandSpec.env`, so the agent cannot override
them there. The real upstream key stays in the harness and the boundary; the MCP server child does
not inherit it and boundary diagnostics are scrubbed of it. Everything else you put in
`CommandSpec.env` or `McpServerSpec.env` is sealed into manifests and bundles verbatim, so keep API
keys out of both.

The Python `typesafe-sdk` honours these variables and needs no code change for the request shapes
covered by the acceptance tests (structured instructions and criteria included). The JavaScript
`@typesafe-ai/sdk` reads the same variables but is not tested here. Other HTTP clients must read
`TYPESAFE_BASE_URL`, send `Authorization: Bearer $TYPESAFE_API_KEY`, and call `POST /v1/systemone`.

## `DecisionSpec`

`Manifest.decisions` is available only for command-agent manifests:

| field | default | meaning |
|---|---|---|
| `upstream` | required | `fixture` imports trusted seeded code; `http` calls a real System One endpoint |
| `fixture` | `None` | required `module:function` for `fixture`; forbidden for `http` |
| `base_url` | `https://api.typesafe.ai` | bare HTTPS origin, or a loopback HTTP origin |
| `model` | `jev-1.13.0` | pinned model placed in every forwarded request and required in the response |
| `max_decisions` | `50` | admitted POST limit, in addition to the shared tool-call budget |
| `request_seconds` | `5.0` | per-request fixture or upstream deadline |
| `max_body_bytes` | `262144` | largest request body accepted by the local endpoint |

`GET /v1/models` is also supported. It is recorded as `decision:models`, but is not a tool event
and does not consume either decision or tool-call budget.

## Perturbations

Both decision perturbations target `decision:systemone`.

`decision_low_confidence` is an after-perturbation at one occurrence (default 0). For each choice
answer with `n >= 2`, let `m` be its largest probability and

```text
c = (n*m - 1) / (n - 1)
```

If `c` exceeds `confidence_max` (default `0.4`), ARCI sets

```text
t = 1 - confidence_max/c
p'_i = (1 - t)*p_i + t/n
```

and reports confidence `confidence_max`. The probabilities still sum to one; mixing never reverses
their order and the `choice` field is preserved, though a cap of 0 or floating-point rounding can
create ties. Noul and score answers are unchanged. This is normally a `falsify` fault
when escalation is an accepted fallback; otherwise it should be `ceiling`.

`decision_unavailable` is a before-perturbation. From `at_occurrence` (default 0) onward, it skips
the upstream and returns HTTP 529 with `{"detail":"arci injected unavailable"}`. It is a
`falsify` fault for agents expected to exhaust retries and fall back safely.

Generic MCP perturbations never apply to decision calls, and decision perturbations never apply
to MCP calls.

## Failures and replay

- A valid real or fixture response, including an upstream 422, is recorded. An injected 529 is an
  ordinary not-ok result that tests the agent's policy.
- Authentication, rate limits, 5xx responses, connection failures, timeouts, malformed upstream
  bodies, and broken fixtures are harness faults (`ERROR`), not agent failures.
- Local 401, 404, 411, 413 and 422 rejections are deterministic client errors. They are not
  recorded or budgeted and set no harness latch.
- Concurrent decisions, or any overlap between a decision and a pending MCP exchange, are
  unsupported and produce a harness fault. One request per connection: pipelined bytes are
  ignored and `Expect: 100-continue` is answered 417.

Replay never calls the fixture or real endpoint. It serves recorded decisions by tool name,
canonical-argument hash and occurrence, rewrites only transport identifiers, and requires exact
consumption. A miss or leftover record is `INVALID`. Decision recordings are included in normal
replay bundles and can be reduced by the existing fault minimiser.

## Real Jev

Use `DecisionSpec(upstream="http")` and put `TYPESAFE_API_KEY` in the harness process environment,
not `CommandSpec.env`. ARCI pins `DecisionSpec.model`, disables proxies, redirects and retries, and
forwards each admitted request once. Real Jev answers are sampled, so repeated live runs can differ.
Recordings contain the full decision state and answers; treat bundles and run stores as sensitive
data.

The v0.5 boundary does not support in-process Python agents directly; run them as command agents
through `arci.mcp_toolset_server`. It also does not support concurrent decisions, overlapping MCP
calls, multiple decision transports, or streamable HTTP MCP. See
[`examples/jev_triage_agent`](../examples/jev_triage_agent) for the offline fixture-backed example.
