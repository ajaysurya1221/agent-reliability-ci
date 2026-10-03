# Results: the triage agent against the live System One endpoint

Planned day-one runs (`docs/design/0004-day-one.md`), produced by
`examples/jev_triage_agent/day_one.sh`. Each run gets a write-up from
`docs/results/TEMPLATE-jev.md` and its sealed store (`manifest.json`, `trials.jsonl`,
`decision.json`) under `<date>/<experiment_id>/`, so `arci gate <store>` re-derives every verdict
from the committed records. Invalid and inconclusive runs stay in the table.

| Run | Arms | Condition | N per arm | A | B | Verdict | What happened |
|---|---|---|---:|---:|---:|---|---|
| `jev-live-b-clean-1` | A vs B | none | 1 | pending | pending | pending | the clean pair; both should PASS |
| `jev-live-b-low_confidence-50` | A vs B | `decision_low_confidence` | 50 | pending | pending | pending | the regression under low confidence |
| `jev-live-a-low_confidence-50` | A vs A | `decision_low_confidence` | 50 | pending | pending | pending | the same agent in both arms; should PASS |
| `jev-live-c-low_confidence-50` | A vs C | `decision_low_confidence` | 50 | pending | pending | pending | the repair; should PASS |
| `jev-live-b-low_confidence-50-node` | A vs B | `decision_low_confidence` | 50 | pending | pending | pending | the official JavaScript SDK, unchanged |
| `jev-live-b-low_confidence-200` | A vs B | `decision_low_confidence` | 200 | pending | pending | pending | the pre-registered design; lists the runs above as prior runs |

Nothing here has been run yet. The fixture numbers in the README (`50/50 vs 0/50`, bounds
`[-1.000, -0.832]`) come from a seeded local endpoint and say nothing about the live model.
