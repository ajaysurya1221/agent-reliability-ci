# Two-reader agent usability rehearsal

Both fresh non-author readers identified the operation-level mismatch with only
the installed CLI, help and recipe, and repeated the workflow on another fixture.
No raw JSONL inspection or implementation access was needed. No author assistance
or interpretation errors were reported. This is agent QA, not human adoption or
retention. Setup reading was excluded from diagnosis timing; the recipe disclosed
the generic retry example, so this was not blinded.

| Reader | Retry diagnosis | Repeat diagnosis | Statistical exits |
|---|---:|---:|---|
| One | 19.164331 seconds | 71.085263 seconds | BLOCK/1; INCONCLUSIVE/2 |
| Two | 21.522030 seconds | 68.445535 seconds | BLOCK/1; INCONCLUSIVE/2 |

All four diagnoses met the predeclared 300-second target after stores were supplied.
Both readers distinguished an absent field from an absent event, retained the
whole-run gate despite selected MATCH/DRIFT or passing trials, and rejected claims
of root cause, benignness or later equivalence from the first difference.

Evidence: [protocol](PROTOCOL.md), [cases](cases.json),
[reader one](reader-one.md), [reader two](reader-two.md), their command transcripts,
and the integrator's exact text/JSON receipts in `results/`. All eight source-file
hashes in the before/after manifests remain identical. The retry store is retained
locally under the temporary path recorded in cases.json and is regenerable with
`arci demo`; a new run need not reproduce recording metadata bytes. The repeat
fixture is already committed in the earlier trace-check rehearsal and unchanged.

Tested product commit: cb2ab9e. Fresh Python 3.13 wheel environment outside checkout,
PYTHONPATH cleared. Initial unpublished candidate version: 0.9.0. Wheel SHA-256:
`ab7fc6e68df13d7b2135e2d7d50e8799a7aacf8253d0cfd37331a4f4e3bc4acd`.
The operator subsequently requested a major release, now targeted at 1.0.0.
These original receipts are preserved; release-package verification is separate.

A single local measurement on the retained 400-trial retry store took 0.547 seconds
for JSON triage and reproduced the receipt exactly. See `results/timing.json`.
This is one fixture measurement, not a general scale-performance claim.
