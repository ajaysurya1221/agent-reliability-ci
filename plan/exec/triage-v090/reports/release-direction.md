# Release direction and research-reference reconciliation

Decision: proceed with native gate-aware triage, and position v1.0.0 as explaining
an ARCI release decision from its recorded evidence. This is a useful integration
of existing ARCI capabilities, not a claim to invent trace comparison, statistical
evaluation or CI. Two independent readers completed the operation-level diagnosis
and repeat exercise without JSONL inspection; that supports this bounded usability
change, not market demand or human adoption.

Primary-source review performed 2026-11-05 UTC by a fresh non-author research agent.
No competitor package was executed. Current source observations are not claims
about installed published artifacts. This is a bounded overlap check, not an
exhaustive market survey or a forecast of GitHub Trending.

| Existing solution | Verified overlap | Consequence |
|---|---|---|
| [EvalView v0.8.1](https://github.com/hidai25/eval-view/blob/v0.8.1/README.md) and [current CLI](https://github.com/hidai25/eval-view/blob/main/docs/CLI_REFERENCE.md) | Snapshot/check trajectories, accepted baselines, CI and reports | Do not rebuild snapshot acceptance or an HTML report platform. |
| [EvalView current model comparison](https://github.com/hidai25/eval-view/blob/5a621c24336d7f4db00fd5d1079c09a0a87656a0/evalview/compare.py) | Concurrent model comparisons, scores, latency and cost | A cross-vendor showcase would duplicate an established direction. |
| [Langfuse comparison](https://langfuse.com/docs/evaluation/experiments/compare-experiments) and [CI](https://langfuse.com/docs/evaluation/experiments/experiments-ci-cd) | Baseline/item comparisons, trace drilldown and regression gating; example validates case completeness and evaluator/dataset identity | Do not claim alternatives only show averages or ignore incomplete cases. |
| [MLflow compare_evaluations](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.genai.html#mlflow.genai.compare_evaluations) | Experimental paired tests, bootstrap intervals and effect sizes; excludes unpaired rows, no cross-scorer multiplicity correction | Statistical comparison exists. Explain ARCI's own prespecified non-inferiority and complete sealed-design rules. |
| [MLflow tracing](https://mlflow.org/docs/latest/genai/tracing/search-traces) and [agent tests](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.genai.html#mlflow.genai.test_agent) | Trace queries/inspection and experimental live scenario simulation | Keep native read-only diagnosis focused. |

ARCI's new command reuses pure `decide` for the complete declared experiment and
`check_traces` for exact selected traces. It supplies deterministic schedule-based
pair selection, hard-violation priority, snapshot binding and bounded context.
It does not create another equality engine, exporter, runner or statistical test.
The practical benefit is removing selection/parsing glue while preserving the
original verdict, denominator, stopping history and historical evidence.

## Complete reference considered

Reference: `plan/research/arci-go-ahead-plan.md` in the original checkout, read in
full. SHA-256: `01b27bbc3fdb0c25927c9ac44922da63273cc08f244a5dbd8c5e05a391f9b0a0`.
The original untracked file is preserved and is not promoted to verified facts.

| Recommendation | Decision and reason |
|---|---|
| Fast onboarding, concrete demo, docs and CI diagnostics | Adopt through the existing packaged offline demo, triage recipe, actual terminal/JSON receipts and exit-preserving CI snippet. |
| Reuse completed trace-check | Adopt: existing comparator/equality and diagnostic results are unchanged; only context mapping is additive. |
| Telemetry and observability | Defer until a concrete external consumer exists; a future exporter should reuse [OpenTelemetry GenAI conventions](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/), currently Development. Runtime changes and dependencies are outside this release. |
| SlopScore and multi-vendor live demo | Defer: they introduce unrelated grading/dependencies and nondeterministic provider setup. They do not solve the demonstrated native triage friction. |
| Release/discovery and feedback | Adopt searchable docs and GitHub/PyPI delivery; distinguish bounded agent QA from adoption. No unsolicited community messages, tracking or popularity claims. |

Correct the reference's inconsistent package names (`ARCI`, `arci-agent`), other
Arci-product assumptions and live-reproducibility claims. Actual package name is
`agent-reliability-ci`. The offline demo needs no key; fresh live model inference
is not deterministic replay. Do not add an unsupported >90% accuracy gate or call
the release production-ready. Stars/downloads and seven-day silence do not measure
successful use or justify a pivot without exposure and attempt data.

## Major release meaning and stop rule

The operator requested a major release after the original candidate was prepared.
Target is v1.0.0 as an explicit [public compatibility commitment](../../../../docs/COMPATIBILITY.md),
consistent with [SemVer](https://semver.org/spec/v2.0.0.html). It does not imply new
safety guarantees or novel algorithms. Existing frozen statistical/replay contracts
remain authoritative. The exact-candidate/main/package gates and 16-hour hard cut
remain. Any unresolved gate prevents merge or publication; no feature expansion
is justified by a hope of trending.
