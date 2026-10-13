CONSULT E1-tiebreak. Two independent proposals for the `arci init` contract exist: plan/exec/consults/E1-astra.md (yours, written from the spec) and plan/exec/decisions/E1-fable.md (the orchestrator's, written blind). They agree on the signature (positional EXPERIMENT_ID; --baseline/--candidate/--toolset/--oracle refs; --task JSON | --task-file; repeatable --fault NAME[:TOOL[:OCC]]; --n default 8; --out default arci.yaml; --force), on validating refs in a child process with the runner's path rule (toolset factory called once, agents and oracle only imported), on one-line errors with exit 3, on the smoke default of 8 and its reasoning, and on `arci run --out` defaulting to `runs`. Decide ONLY the five differences below. For each, answer with one choice ("A" = Astra's, "F" = Fable's, or a one-line merged wording) and one sentence of reason; then one closing paragraph (at most 120 words) on anything that must be true for both. Read both files first; also read plan/exec/tasks/04.md and src/arci/cli.py main() (error printing) and src/arci/report.py (how arm labels appear in the Markdown report) before deciding C.

A. Success stdout. Astra: exactly one line `arci run arci.yaml` (the path shell-quoted). Fable: two lines, `wrote arci.yaml  (smoke design: n_per_arm=8, expect INCONCLUSIVE)` then `next: arci run arci.yaml`.
B. YAML header comment. Astra: 4 lines (smoke design: expect INCONCLUSIVE; run arci plan before a confirmatory N / Default: 8 trials per arm; this scaffold does not establish confirmatory power / Plan before trials: arci plan --help / Never extend this experiment based on its verdict). Fable: 6 lines including the schema pointer, "Under the default rule PASS is impossible below N=42 and BLOCK below N=8" (which Astra showed is imprecise: it holds for two perfect arms / a total collapse), a concrete `arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK` example, and "Changing anything below makes a new experiment; arci run seals it before the first trial". Give the final header text verbatim if merged.
C. Arm labels and candidate_id for bare refs. Astra: labels `baseline` and `candidate`, candidate_id left at the Manifest default (""). Fable: label = `<last module segment>.<function>` (e.g. `v1.run`, `v2.run`) and candidate_id = the full ref string.
D. Accepted fault names. Astra: only the built-ins tool_timeout, tool_error_once, empty_result. Fable: built-ins or an importable `module:function` custom fault (the Manifest allows it; validation imports it in the child).
E. Task id. Astra: task_id = EXPERIMENT_ID, no flag. Fable: `--task-id` flag with that default. (Fable concedes: drop the flag unless you see a reason to keep it.)

Format exactly:
A: <choice> — <reason>
B: <choice> — <reason> (+ header text if merged)
C: <choice> — <reason>
D: <choice> — <reason>
E: <choice> — <reason>
Closing paragraph.
