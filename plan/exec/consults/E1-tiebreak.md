A: A — A single shell-quoted command is directly copyable and matches T04’s success-output contract.

B: Retain Astra’s four lines and prepend the schema pointer — This preserves actionable guidance without incorrect universal thresholds or assumed planning rates.
```yaml
# arci experiment descriptor. Schema: `arci schema`.
# smoke design: expect INCONCLUSIVE; run arci plan before a confirmatory N
# Default: 8 trials per arm; this scaffold does not establish confirmatory power.
# Plan before trials: arci plan --help
# Never extend this experiment based on its verdict.
```

C: A — The Markdown report uses fixed Baseline/Candidate headings rather than arm labels, and an import ref does not identify an immutable code version.

D: A — Limiting init to `tool_timeout`, `tool_error_once`, and `empty_result` keeps `NAME[:TOOL[:OCC]]` unambiguous; custom factories remain available through handwritten descriptors.

E: A — Defaulting task_id to EXPERIMENT_ID satisfies T04 without adding a flag needed only for later descriptor editing.

Both must validate references in a bounded child using the runner’s path rule, revalidate generated YAML before success, and preserve the existing `main()` error formatting: init validation failures become `error: CliError: init: …`, with exit 3 and empty stdout. This was a read-only review; no files changed or tests ran. Before T04, reconcile one unlisted conflict: Astra combines repeated faults into one condition, while Fable creates separate conditions, changing K and the applicability of K=1 smoke and planner reasoning.