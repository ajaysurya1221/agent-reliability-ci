# 0004: ready for Jev day one (v0.6)

Decision by the lead architect, reviewed by the senior consultant (gpt-6-astra, xhigh) on
2026-09-22. Nothing here was run against Jev: the owner has no key. Every rule is derived from the
vendor documentation, the two official SDK sources and the AI Gateway documentation, and is
enforced by tests against a fake upstream shaped like them.

## What day one looks like

```bash
export TYPESAFE_API_KEY=...            # or an AI Gateway key
arci preflight manifest.json           # 0 ready, 2 pinned model missing (ids printed), 3 anything else
arci run manifest.json --out runs      # decisions.upstream = "http"
arci report runs/<experiment>          # gate, failure clusters, tokens, estimated cost
```

## Facts that drove the decisions

- The gateway path: `https://ai-gateway.vercel.sh/typesafe`, model `typesafe-ai/jev`, an extra
  `provider_metadata` object on every response, errors as `{"message","error_type"}`.
- Both SDKs retry 408/429/5xx twice with backoff and a 10 s per-attempt timeout; both honour
  `retry-after` and `retry-after-ms`; both ignore unknown response fields; both read the same
  three environment variables.
- The vendor limit is 1,200 requests per minute and "adjusting dynamically".

## Decisions and the trade-offs behind them

1. **A path prefix is legal in `base_url`.** Before v0.6 the gateway could not be used at all.
2. **Validation tolerates what the SDKs tolerate.** Unknown fields were already ignored; the
   change is the probability-sum tolerance (1e-3) and a fixed message per transport fault.
3. **Pacing lives in the parent, per trial start.** A per-request permit through parent IPC would
   bound agents that decide many times per trial; it would also add a bidirectional protocol
   between parent and boundary. The example agent decides once per trial, and `max_decisions`
   bounds the rest, so trial-start pacing with a documented "divide the rate by k" rule is the
   smaller correct tool. The consultant preferred per-request permits; recorded as future work.
4. **One bounded wait on 429/529, recorded, never hidden.** The v0.5 rule "no proxy retries"
   protected faithful attempt counts from the agent's point of view. A wait-and-resend inside one
   admitted attempt keeps that (one `tool_start`, one occurrence, one record) while letting a
   400-trial run survive a transient limit that would otherwise invalidate it. The raw snapshot
   records `attempts` and `first_status`, so nothing is concealed. `request_seconds` stays 5 s so
   the wait fits inside the SDKs' timeout; a client that gives up first would retry into a busy
   boundary and hit the serial rule.
5. **The raw upstream answer is recorded beside the served one.** Cheap, useful for audits and
   for a future calibration audit. It does NOT enable counterfactual minimisation: an agent's tool
   sequence depends on the answer it got, so a recording cannot be re-perturbed faithfully.
   Live-upstream minimisation therefore reports "reduced", never "1-minimal". The consultant also
   found that an ERROR on a single-removal candidate was being read as "failure lost"; it now
   blocks the 1-minimal claim.
6. **Preflight is a separate command, not a trial.** It answers the three questions that decide
   whether a run can start (key, endpoint, pinned model) and leaves a credential-free receipt.
7. **Cost is an estimate at list price.** Fixtures and replays are free; only recorded input
   tokens are priced.
8. **The JavaScript SDK gets its own agent and test.** Pinned `@typesafe-ai/sdk` 0.6.0 as an
   example-only dependency; the test runs wherever `node` and the package are present, and CI
   installs it.

## Not in v0.6

Per-request pacing through parent IPC; counterfactual replay of recorded decisions; adaptive or
token-rate control; account-wide limits shared across runs; a calibration audit (needs labelled
real outputs and a key).
