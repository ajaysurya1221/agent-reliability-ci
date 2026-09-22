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

The Python `typesafe-sdk` and JavaScript `@typesafe-ai/sdk` honour these variables and are exercised
unchanged by the acceptance tests. Other HTTP clients must read `TYPESAFE_BASE_URL`, send
`Authorization: Bearer $TYPESAFE_API_KEY`, and call `POST /v1/systemone`.

## `DecisionSpec`

`Manifest.decisions` is available only for command-agent manifests:

| field | default | meaning |
|---|---|---|
| `upstream` | required | `fixture` imports trusted seeded code; `http` calls a real System One endpoint |
| `fixture` | `None` | required `module:function` for `fixture`; forbidden for `http` |
| `base_url` | `https://api.typesafe.ai` | HTTPS origin with an optional path prefix, or loopback HTTP for tests |
| `model` | `jev-1.13.0` | pinned model placed in every forwarded request and required in the response |
| `max_decisions` | `50` | admitted POST limit, in addition to the shared tool-call budget |
| `request_seconds` | `5.0` | per-request fixture or upstream deadline |
| `max_body_bytes` | `262144` | largest request body accepted by the local endpoint |
| `max_requests_per_minute` | `600` | `http` only: parent-paced trial starts per minute; `0` disables pacing |

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

and reports confidence `confidence_max`. The probability sum remains within the accepted tolerance; mixing never reverses
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
not `CommandSpec.env`. ARCI pins `DecisionSpec.model` and disables proxies and redirects. It does
not retry arbitrary failures; only the documented bounded 429/529 wait can resend once. Real Jev
answers are sampled, so repeated live runs can differ. Recordings contain the full decision state
and answers; treat bundles and run stores as sensitive data.

The decision boundary does not support in-process Python agents directly; run them as command agents
through `arci.mcp_toolset_server`. It also does not support concurrent decisions, overlapping MCP
calls, multiple decision transports, or streamable HTTP MCP. See
[`examples/jev_triage_agent`](../examples/jev_triage_agent) for the offline fixture-backed example.

## Day one with a key

Gateway behaviour, model identifiers, prices and provider limits are derived from documentation
dated 2026-09-22. Tests use fixtures and fake upstreams; Jev was not run.

Use a versioned model while tuning policy thresholds. For TypeSafe directly, use the configured
API origin and pin the available versioned Jev id; through Vercel AI Gateway, use base URL
`https://ai-gateway.vercel.sh/typesafe` and model `typesafe-ai/jev`.

```bash
arci preflight manifest.json
arci run manifest.json --out runs
arci report runs/<experiment>
```

`preflight` exits 0 when the key, endpoint, pinned model and smoke decision validate; 2 when the
pinned model is absent (available ids are printed); and 3 for missing credentials, a non-HTTP
manifest or any endpoint/response failure. Save its credential-free JSON receipt with the run.

For HTTP upstreams, `run_experiment` paces trial starts at `max_requests_per_minute` across workers.
The parent spaces trial starts, not individual requests. Budget the maximum upstream sends per trial,
including SDK retries, the boundary's possible resend and model discovery, and divide the provider
rate by that number. This does not guarantee an instantaneous provider request rate. Standalone
trials, preflight and minimisation are unpaced. A 429 or 529 permits one bounded wait and one identical resend; the single recorded decision
keeps `upstream.attempts` and `upstream.first_status`. A second 429/529 is a harness error, not an
agent failure. A 429 means the provider or account rate limit was exceeded; 529 means the provider
is overloaded. Keep `request_seconds` below the SDKs' 10-second per-attempt timeout (the default is
5 seconds), so the SDK does not retry while the boundary is still handling the first request.

Live answers are sampled, and aliases such as `jev-latest` can move; pin the model version used to
set confidence thresholds. Reports sum recorded tokens and show estimated cost at the list price
read on 2026-09-22, not billed spend; fixtures and replays cost nothing. Completed upstream decision records also seal the
raw validated response under `ToolResult.value.upstream` before after-perturbations. The request
state is sealed separately in the tool-call arguments, so stores and bundles may contain private
customer data. Live minimisation is reported only as `reduced`, never `1-minimal`, because a sampled
answer or an ERROR on a removal cannot establish minimality.

The example includes both the stdlib Python agent and a Node 20+ agent using
`@typesafe-ai/sdk` 0.6.0 with `new TypeSafeClient()` and environment-only configuration. Select it
with `build_manifest(..., runtime="node")` after running `npm ci --prefix
examples/jev_triage_agent`.
