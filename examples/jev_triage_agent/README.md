# Jev-style support triage

This offline example tests a command agent that makes one System One decision over HTTP and then
acts through MCP. Agent A applies the TypeSafe confidence-gating pattern: every autonomous action
needs confidence 0.6, a refund needs 0.85, and uncertainty or provider failure escalates to a
human. B is the regression: it silently returns in those cases. C restores escalation.

`agent.py` uses only the Python standard library. `agent.mjs` mirrors it with the official
`@typesafe-ai/sdk` 0.6.0 and Node 20 or newer. ARCI supplies the same `TYPESAFE_BASE_URL` and
`TYPESAFE_API_KEY` variables both official SDKs read, and the acceptance suite exercises each SDK
unchanged against the harness-owned boundary.

## Run

From the repository root:

```console
.venv/bin/python examples/jev_triage_agent/hero_demo.py --n 50
```

Measured on 2026-09-22 (15-core laptop, about 20 s for all six steps, N=50 per arm):

- clean pair: A and B both PASS
- A versus B under `decision_low_confidence`: 50/50 vs 0/50, bounds on the difference
  [-1.000, -0.832], BLOCK (exit 1)
- A versus A: 50/50 vs 50/50, bounds [-0.084, 0.084], PASS (exit 0)
- reduced failure and replay: the minimiser keeps `decision_low_confidence` and removes the benign
  `empty_result` (1-minimal, 2 trials); the reduced bundle replays REPRODUCED with no provider running
- A versus C: 50/50 vs 50/50, PASS (exit 0); C also passes B's exact reproducer against the seeded
  fixture in RECORD mode, which does not exercise Jev

The six steps show the clean run hiding the regression, the frozen experiment blocking B, an
aligned trace diff, fault minimisation, offline replay, and C passing the same fault.

## Limits

The default experiment uses a seeded fixture, not Jev. The fixture is useful for a deterministic
CI example; it says nothing about Jev's accuracy or calibration. The low-confidence perturbation
mixes a choice distribution toward uniform and therefore never changes its winner. Escalation is
an oracle-approved fallback, so this experiment tests whether the workflow hands uncertainty to a
human, not whether escalation solves the ticket automatically.

To use real Jev, build the same manifest with `DecisionSpec(upstream="http")` and provide
`TYPESAFE_API_KEY` only in the harness environment. Real answers are sampled and may not replay
the same agent path.

## Synthetic miscalibration

`calibrated_manifest()` is an offline fixture option. Its task puts
`{"calibration":{"ambiguous_share":x,"confidence":c}}` on each public ticket; a seeded share `x`
is treated as ambiguous, and the fixture selects a wrong department with probability `1 - c`
while reporting confidence `c`. Selection is deterministic for each seed and decision occurrence.
This is synthetic test data for confidence-gating regressions, never a claim about Jev's behaviour
or calibration.
