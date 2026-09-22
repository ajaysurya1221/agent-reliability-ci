# Jev / System One research notes (2026-09-22)

Sources: typesafe.ai blog "Introducing System One Models & Jev" (2026-09-15), docs.typesafe.ai
(llms.txt index, api.md, models.md, confidence.md, model-jaggedness/jev-1.13.md, patterns,
cookbooks), PyPI metadata, the installed `typesafe-sdk==0.7.1` and `system-one-adapter==0.2.0`
sources (scratchpad `jev-sdk/.venv/lib/python3.13/site-packages/{typesafe_sdk,system_one_adapter}`),
third-party write-ups (LangChain, TrueFoundry, MindStudio, dev.to/valyu, Vercel).

## What Jev is

- "System One model": a non-autoregressive model that takes **state** (text / JSON object / array)
  plus a map of **typed questions** and returns **typed answers with probabilities** in one parallel
  pass. No text generation, no tool calling, no conversation. Output schema is fixed by the
  question types, so a *malformed* answer is impossible ("0% schema errors"); a *wrong* answer is
  not.
- Trained with "Reinforcement Learning for Calibrated Decisions (RLCD)"; the headline claim is
  calibrated probabilities/confidence ("higher confidence means higher accuracy"). No independent
  calibration audit exists yet (TrueFoundry: "the one no outside party has tested yet").
- Latency 70–500 ms end to end (docs cookbook: 111 ms mean). Input $0.042/MTok, output free.
  Rate limits 250k tokens/s, 1,200 req/min, "adjusting dynamically".
- Model ids: `jev-1.13.0`; aliases `jev-latest`, `jev-preview` (both -> 1.13.0). Aliases move;
  the response carries the versioned id actually used. Pin versions when tuning thresholds.
- Context: 64k tokens per request (state + all questions); 32k for state + longest question.
- Access: early access / waitlist; keys from console.typesafe.ai; also via Vercel AI Gateway.
  Ajay has no key (no `TYPESAFE_*` env on this machine).
- Stochastic, not deterministic: the self-consistency cookbook repeats identical requests 15x and
  reports noul std dev ≈ 0.0102 per question (lower than LLMs at temperature 0, but nonzero).
  There is no seed or temperature parameter in the API.

## The three primitives

| Type | Ask | Answer fields |
|---|---|---|
| `noul` | "Is this statement true?" (optional `criteria.true` / `criteria.false`) | `noul: float` in [0,1] = P(yes). No `confidence` field. |
| `choice` | pick one of up to 255 `criteria: {name: description}` | `choice: str`, `probabilities: {name: float}`, `confidence: float` |
| `score` | rate against 2–10 ordered `criteria: [level descriptions]` | `score: float` (probability-weighted, may sit between levels), `legend: {index: desc}`, `probabilities: {index: float}`, `confidence: float` |

Confidence = concentration of the distribution: for three options the docs give
`(3 * max_p - 1) / 2`; in general 1.0 when all mass is on one outcome, lower as it spreads.
Docs' routing guidance: floor 0.6 (below -> human), 0.85+ for high-stakes autonomous actions.
"The correct threshold values depend on your domain and the performance of the model for your use
case" — i.e. thresholds are tuned per deployment and are exactly the kind of logic that regresses.

## HTTP API (what a proxy must speak)

```
POST {base_url}/v1/systemone        Authorization: Bearer <key>   Content-Type: application/json
GET  {base_url}/v1/models           -> {"models": [{"name","description","release_date"}]}
```
Request body: `{"state": str|object|array, "model": "jev-latest", "questions": {name: Question}}`.
The SDK may add arbitrary top-level keys via `extra_body` (must be forwarded untouched).
Response: `{"model": "jev-1.13.0", "answers": {name: Answer}, "usage": {"input_tokens", "output_tokens"}}`.
Answer JSON: `{"type":"noul","noul":0.95}`; `{"type":"choice","choice":"billing","probabilities":{...},"confidence":0.8}`;
`{"type":"score","score":1.03,"legend":{"0":"Calm",...},"probabilities":{"0":0.4,...},"confidence":0.5}`
(score keys are strings on the wire; the SDK coerces to int). The SDK ignores unknown answer types
and extra fields (`extra="ignore"`), validates strictly otherwise.
Errors: 401 auth, 422 validation (`{"detail": [{loc,msg,type,input,ctx}]}`), 429 rate limit,
529 overloaded. SDK default `RetryPolicy(max_retries=2, backoff_initial=0.5, backoff_max=5.0)`,
retries 429/5xx; sends a retry-count header on retries; reads a request-id response header.
Default per-operation timeout 10 s.

## SDK facts that matter for integration

- `typesafe-sdk` (MIT, py>=3.10): `TypeSafeClient(api_key=None, base_url=None, default_model=None,
  retry=None, timeout=None, default_headers=None)`; resolution order arg -> env -> default.
  **Env vars: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_LOG_LEVEL`.**
  Default base URL `https://api.typesafe.ai`. Deps: httpx2, pydantic>=2.12, tenacity.
- So any agent using the official SDK (Python or JS: `@typesafe-ai/sdk` reads the same `ENV`)
  can be pointed at a harness-owned loopback endpoint **with zero code changes**, and the real key
  never needs to be in the agent's environment.
- `system-one-adapter` (MIT): a drop-in `SystemOneAdapterClient` with the same `system_one(state,
  questions)` API backed by any OpenAI-compatible endpoint (incl. Ollama) or Anthropic; emits
  `SystemOneResponse` + `usage.latency`, retries on malformed structure, can normalise
  probabilities. Useful as a *local emulator* when no Jev key is available.
- Official agent skill: `claude plugin marketplace add typesafe-ai/skills`;
  `claude plugin install typesafe@typesafe-ai` (or `npx skills add typesafe-ai/skills --skill typesafe-ai`).
  LangChain: `langchain-typesafe` (`TypeSafeClassifier`, `ModelRouterMiddleware`, tool-guardrail
  middleware that classifies risky tool calls before execution).

## Known jagged edges (jev-1.13, from the vendor)

Literal reading of instructions; no arithmetic or counting; dates read as text; multi-hop
indirection degrades; irrelevant state distracts; adversarial content in state steers outputs
(state is not treated as untrusted); contradictory instructions; no structural invariants across
separate questions; no generation.

## Vendor evals (self-reported, no public data)

Four "workflow" tasks (security incident triage, **agent trace observability**, invoice
processing, customer service), labels = average of GPT-6 Astra and Fable 5.1 at high thinking.
Jev: 61.7% / 71.6% / 61.8% / 76.0% accuracy at $0.0001–0.0011 per case and 0.3–0.5 s. Competing
LLMs were run through TypeSafe's own adapter. Claim: "every model is more accurate, cheaper and
faster in the workflow than it is with the same policy as a prompt."

## How people are using it (patterns)

Confidence-gated routing; speculative fan-out (ask everything in one call, decide in code);
composite scoring; intent routing (deterministic / specialist LLM / human); cascades
(Jev -> verify -> reasoning model); guardrails for LLM input/output; citation checks; RAG
passage classification; re-ranking; function calling with closed-set arguments; tool-call risk
classification inside agent harnesses. "Code owns the workflow; the model supplies programmable
common sense."
