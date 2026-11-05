# ARCI v0.9.0: approved failure-triage delivery

Approved by the operator in Codex on 2026-11-05, including reviewed GitHub
delivery, release-only fallback, and the narrow packaging re-freeze. Base:
`f039e1ddd07011a6018b88171cb51d5be3d63b26`. Budget: 16 working hours.

## Global constraints

- ARCI only. No dependencies, semantic frozen amendments, imports of recorded
  agents/oracles, live models, outreach, telemetry, importers or automatic replay.
- Preserve statistical/replay/runner/storage behavior, existing comparator output,
  the contracted README first screen, and historical evidence byte for byte.
- Only the orchestrator changes Git state or uses network services. Workers use
  installed `.venv/bin` tools, own only their listed paths, and do not revert others.
- Publication is authorized after exact-candidate review/CI and exact-main CI.
  Existing tags/distributions are immutable. Partial publication never licenses
  rebuilding/re-uploading the same version.
- Package re-freeze is limited to pyproject/lock version metadata and a new
  release design record with corresponding FROZEN entries. Resolved dependency
  versions remain unchanged. All other existing frozen hashes remain identical.

## Product contract

`arci triage RUN_DIR [--trial CANDIDATE_ID] [--format text|json]`

Read through `load_run`, derive the complete gate with pure `decide`, and preserve
all original counts, conditions, look history and verdict. Invalid stores and
run-level ERROR never get paired-trace diagnosis. No source or summary writes.

Group candidate FAIL records by `(condition_id, failure_fingerprint)`, keeping
unfingerprinted failures explicit and separate from any real string fingerprint.
Show at most three groups, with total/shown/omitted group counts. Sort by:
1. Groups containing candidate hard violations (including ceiling conditions).
2. Groups in **gating** BLOCK conditions.
3. Other gating groups.
4. Descriptive ceiling groups.
Within a tier sort by descending group count, condition ID, fingerprint (with a
stable distinct ordering for missing fingerprint). For a hard-violation group,
choose among actual hard-violating trials first. Then prefer paired baseline PASS,
then scheduled order. Resolve pairs from schedule identities, never ID parsing.
Only observed scheduled trials are candidates, respecting valid early stopping.

`--trial` overrides automatic selection and selects one unique candidate trial,
including PASS. A baseline-arm ID, missing ID or nonunique selection is INVALID.
Failure-group counts remain separate from selected-pair counts in this mode.
No candidate FAILs means no automatic comparison, not a claim of reliability.

`check_traces` remains the only comparison and selected-event validation engine.
For each selected pair invoke it on the same run directory. Before adding context,
require both returned source manifest/trial/decision hashes to equal the initial
snapshot. Any mismatch, INVALID comparison or diagnostic validation failure
produces INVALID/3 and no contextual interpretations. Never combine mixed evidence.

An additive helper beside the existing projection maps normalized position to
containing event/seq/tool/occurrence, terminal record or absent step. For finishes,
resolve occurrence through the validated call link. Derive differing-value
presence from the comparator's hash being non-null (JSON null is present). Do not
add pointer evaluation or another equality rule. Tool names are display-bounded
and controls escaped. No argument/result values, raw failure details or annotations.
Names, pointers and hashes can disclose information: do not promise sanitization.

Exit is the unchanged gate exit 0/1/2/3 unless diagnosis is INVALID, then 3.
DRIFT never changes the statistical exit. First difference is not root cause or
proof of regression, benignness, or equality of later behavior.

## Shared interface

Lane A implements in `arci.triage`:

```python
triage_run(run_dir: Path | str, *, trial_id: str | None = None) -> TriageResult
render_triage(result: TriageResult, *, output_format: Literal["text", "json"] = "text") -> str
```

`TriageResult` is immutable and exposes `exit_code: int`. JSON top-level fields:
`schema_version` (`arci-triage/1`), `status` (`OK` or `INVALID`), `reason`,
`exit_code`, `gate`, `group_counts`, `groups`, `selected_pairs`, `limitations`.
`gate` is null if unavailable, otherwise includes `verdict`, `exit_code`,
`manifest_sha256`, `trials_sha256`, `decision_sha256`, complete condition counts,
decision configuration and reached-look history. Error reasons must not dump raw
parser exceptions or user payloads. `group_counts` has `total`, `shown`, `omitted`.
Each selected pair includes candidate/baseline IDs and original outcomes, the
unchanged TraceCheckResult serialization under `comparison`, and context for its
first difference. Lane A locks remaining nested names in its report before Lane B
adds exact installed JSON assertions. No public schema.py changes.

## Task 1: core implementation

Owner Lane A: `src/arci/triage.py`, additive helper in `src/arci/trace_check.py`,
`tests/unit/triage/**`, and `plan/exec/triage-v090/reports/core.md`.
Read AGENTS and its prerequisite contracts. Write and observe meaningful failing
tests before implementation. Cover stable order/selection, ceiling hard priority,
early stops, malformed sources, concurrent source changes, all gate exits,
explicit passing trial, no failures, missing/null/event/terminal contexts,
incomplete/crashed calls, and payload canaries. Keep existing trace-check receipt
bytes unchanged. No Git/network operations. Report actual test evidence and limits.

## Task 2: CLI and installed package

Owner Lane B: `src/arci/cli.py`, `tests/unit/cli/test_triage.py`,
`.github/scripts/triage_smoke.py`, `.github/scripts/wheel_smoke.sh`, and
`plan/exec/triage-v090/reports/cli.md`.
Wire the shared interface without independent selection/comparison. Test help,
arg errors, text/JSON, all gate exits, invalid diagnostic overrides, no writes and
unaffected legacy command behavior. Exercise actual installed triage outside the
checkout with PYTHONPATH cleared, import provenance inside the fresh environment,
and real source-store hashes. Reuse the shared demo stores and stdlib/installed
ARCI only. Existing trace-check smoke remains intact. No Git/network operations.

## Task 3: integration, evidence and release

Integrator owns recipe, below-fold README, roadmap, changelog, version/citation,
release ADR/FROZEN, and execution records. Two fresh non-author agent readers get
only help/recipe/stores. Each identifies the operation mismatch without parsing
JSONL, preserves gate/INCONCLUSIVE interpretation, and repeats on a different
fixture. Target five minutes per diagnosis after stores exist. Retain attempts,
commands, timing, assistance and errors. This is agent QA, not human adoption.

Reproducible demo: existing `arci demo --workers 4 --keep arci-triage-demo`, then
triage the candidate B reserve-timeout-200 store. Expected whole-run BLOCK/1 with
baseline reserve retry versus candidate confirm at the selected recorded position.
Do not rewrite the demo, rerun until green, or claim causality from that position.

Required verification: targeted tests, complete suite, Ruff format/check, strict
types, frozen/protected hashes, figure check, archived decision/planner reproduction,
the prior 3-receipt/29-hash verifier, and four hosted installed-wheel jobs. Fresh
review covers spec compliance and code quality plus whole-branch release boundaries.

Git delivery: sprint branch -> draft PR -> independent review and exact-head checks
-> merge commit -> exact-main CI -> annotated v0.9.0 -> existing build/smoke/OIDC
workflow -> downloaded PyPI bytes checked against workflow hashes -> clean install,
demo/triage/trace statuses -> GitHub release with the same artifacts/checksums.

## Schedule and hard cuts

Day 1 hours 0-1: baseline, interfaces, release access. Hours 1-6: two disjoint code
lanes, integrator docs/preflight. Hours 6-8: integrated vertical slice. If hashes,
contexts and exits do not pass, keep work and switch to release-only candidate from
verified main. Day 2 hours 0-3: independent review and agent QA/corrections. Hours
3-8: feature freeze, full verification and GitHub/release delivery. At hour 16,
unresolved gates leave PR unmerged or version untagged. Never weaken checks.

Fallback releases already-merged trace-check with accurate installation/availability
docs and the same gates. It does not claim triage completed. No human participant
or outreach is required. No claim of adoption, retention or superiority follows.

## Approved release-target amendment — 2026-11-05

After implementation and initial agent QA, the operator requested a major release
and instructed the orchestrator to pivot if the workflow reinvents an existing
solution without useful value. Target is now **v1.0.0**, subject to an independent
primary-source overlap review. The two-day budget, feature boundary and release
gates remain. The original v0.9.0 candidate/QA records are retained unchanged; they
are prepublication evidence, not a released version. Only current packaging,
release metadata and the new unpublished release ADR are revised/re-frozen.
