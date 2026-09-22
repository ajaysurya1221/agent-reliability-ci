# Jev-style support triage

This offline example tests a command agent that makes one System One decision over HTTP and then
acts through MCP. Agent A applies the TypeSafe confidence-gating pattern: every autonomous action
needs confidence 0.6, a refund needs 0.85, and uncertainty or provider failure escalates to a
human. B is the regression: it silently returns in those cases. C restores escalation.

The agent uses only the Python standard library. An agent using the official `typesafe-sdk` or
`@typesafe-ai/sdk` works unchanged because ARCI supplies the same `TYPESAFE_BASE_URL` and
`TYPESAFE_API_KEY` variables.

## Run

From the repository root:

```console
.venv/bin/python examples/jev_triage_agent/hero_demo.py --n 50
```

Expected measured results (filled after the boundary implementation is integrated):

- clean pair: `<measured>`
- A versus B under `decision_low_confidence`: `<measured>`
- A versus A: `<measured>`
- reduced failure and replay: `<measured>`
- A versus C: `<measured>`

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
