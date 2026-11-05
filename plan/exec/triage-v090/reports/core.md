# Lane A core implementation report

Owned checkout: `/Users/ajay/Developer/.arci-worktrees/triage-v090`.
Starting source commit supplied by orchestrator: `16e8a1a`.

## Locked interface and JSON shape

Public API:

- `triage_run(run_dir: Path | str, *, trial_id: str | None = None) -> TriageResult`
- `render_triage(result: TriageResult, *, output_format: Literal["text", "json"] = "text") -> str`
- `TriageResult` is a frozen dataclass. Its `exit_code` property returns the original gate exit unless diagnosis is INVALID, when it returns 3.

JSON top-level fields: `schema_version` (`arci-triage/1`), `status` (`OK`/`INVALID`), `reason`, `exit_code`, `gate`, `group_counts`, `groups`, `selected_pairs`, `limitations`.

`gate` is null if unavailable; otherwise it is the complete original `GateDecision.model_dump(mode="json")`, retaining all original fields, counts, bounds, condition decisions, decision configuration, reached-look history, reasons, prior runs, and `record_sha256`. It adds `decision_sha256` as an alias of that original decision seal. Gate values are never reconstructed from the selected groups. A run-level ERROR returns INVALID, retains that complete gate, exits 3, and has no selected pairs or contexts.

`group_counts = {total: int, shown: int, omitted: int}`.

Each shown group:

```json
{"condition_id":"...","failure_fingerprint":null,"count":1,"hard_violation_trials":0,"is_gating":true,"condition_verdict":"INCONCLUSIVE","selected_candidate_id":"..."}
```

`failure_fingerprint` is string or null, with null distinct from every string including `""` and `"<missing>"`. `hard_violation_trials` counts group members with at least one hard violation. Gate condition `candidate_hard_violations` remains unchanged and counts actual violations under the existing gate rule. `selected_candidate_id` is the automatic group representative; explicit `--trial` does not modify these group summaries.

Each selected pair:

```json
{"candidate_trial_id":"...","baseline_trial_id":"...","candidate_outcome":"FAIL","baseline_outcome":"PASS","comparison":{},"first_difference_context":null}
```

`comparison` is the unchanged dataclass serialization of `TraceCheckResult`, with its existing schema version, fields, reason, source metadata, hashes, pointer, and limitations. For DRIFT, `first_difference_context` is `{baseline: context, candidate: context}`. MATCH has null context. Each context:

```json
{"location":"event","event_kind":"tool_finish","seq":2,"tool":"fetch","occurrence":0,"value_present":false}
```

`location` is `event`, `terminal`, or `absent`; `event_kind`, `seq`, `tool`, and `occurrence` are nullable. Event location remains present even if a nested differing subtree is absent. `value_present` derives exclusively from the corresponding non-null comparator digest, so JSON null is present. Finish occurrence resolves through its matching validated tool-start call. Tool display is ASCII/control escaped once, at most 120 characters, with `...` marking truncation. No pointer evaluation or second comparison/equality algorithm was introduced.

## Behavior implemented

- Load native stores through `load_run`, derive the complete gate through pure `decide`, and stop diagnosis on invalid stores or run-level ERROR.
- Candidate FAIL groups sort by actual group hard violations (including ceiling groups), other groups in gating BLOCK conditions, other gating groups, then descriptive ceilings; ties use descending count, condition ID, and fingerprint with distinct missing ordering.
- At most three shown groups/pairs in automatic mode. Hard-violating representatives take priority, followed by paired baseline PASS, then schedule order.
- Pair lookup uses schedule pair identities; selection uses observed schedule entries, including valid early stops. No trial-ID parsing.
- Explicit candidate PASS or FAIL selection compares one unique candidate pair; baseline, missing, duplicate, or invalid-store selections return INVALID.
- Both comparison sources must match initial manifest/trial/decision hashes, experiment/trial identity, original outcome, and original gate status before any context is constructed. Any mismatch or INVALID comparison discards every selected pair/context, including any accumulated earlier pair.
- No candidate FAILs means no automatic comparison, with an explicit limitation against reliability inference.
- Text is gate-first and readable: configuration/stop summary, condition counts/roles/verdicts, group totals and summaries, pair identities/outcomes, first step/pointer, separate containing-record context lines and presence, and full provenance hashes. Complete gate/unchanged comparison objects remain in JSON. Limitations print once by distinct text.
- No store/summary writes, recorded target imports, live execution, dependency changes, Git mutations, frozen edits, or network operations.

## Red/green evidence

1. Initial test collection attempted a cross-test fixture import and failed because the `tests` directory is not an importable package. Corrected by making triage fixtures self-contained within the owned test file; no production change.
2. Observed RED: `.venv/bin/pytest tests/unit/triage -q` produced **22 failed** tests, all reporting the missing `arci.triage` API after fixtures successfully built native sealed stores.
3. Implemented the bounded core; same focused run became GREEN (**22 tests**).
4. Added escaping and source-identity checks. Observed RED: exact escaping was doubled, and altered comparator trial identity was accepted. Fixed display escaping and snapshot identity binding; focused tests became GREEN.
5. Orchestrator requested readable default text and explicit truncation markers. Observed RED: gate was not the first line, and 121-character ASCII tool names truncated without `...`. Implemented the readable renderer and marked truncation; tests became GREEN.
6. Additional adversarial coverage includes all six source-hash combinations, actual store rewrite during a later pair, missing/empty/real fingerprint ordering, independent explicit selection counts, gating BLOCK precedence, reversed store order, colon-rich condition IDs, nonzero finish occurrence lookup, malformed/seal/duplicate/missing/ERROR/invalid-event cases, no writes and payload canaries, incomplete crash/timeout/budget traces, valid early stopping and complete history, PASS gate + DRIFT exit 0, explicit PASS, and no-failure INCONCLUSIVE.

Final focused commands:

```text
.venv/bin/ruff format src/arci/triage.py src/arci/trace_check.py tests/unit/triage
1 file reformatted, 2 files left unchanged

.venv/bin/ruff check src/arci/triage.py src/arci/trace_check.py tests/unit/triage
All checks passed!

.venv/bin/basedpyright src/arci/triage.py src/arci/trace_check.py tests/unit/triage
0 errors, 0 warnings, 0 notes

.venv/bin/pytest tests/unit/triage tests/unit/trace_check tests/unit/cli/test_trace_check.py -o addopts='' -q
158 passed in 0.83s
```

Final focused total: 38 new triage tests and 120 existing trace-check/core CLI tests. Existing comparator projection, comparator dataclasses, equality/difference rules, and renderer behavior were not modified; `trace_check.py` changes are the additive context dataclass/helper and stdlib JSON import. Existing trace-check tests pass. No new type suppressions.

## Limits and risks

- Full-suite/exact-head/installed/release acceptance belongs to the orchestrator; this report is focused worker evidence only.
- Existing receipt bytes need the orchestrator's independent baseline receipt check; a green existing comparator suite is not itself an independently retained byte receipt.
- Provenance proves snapshot consistency, not execution authentication. Tool names, identifiers, pointers, fingerprints, and hashes can disclose information; output explicitly avoids promising sanitization.
- The first difference is not causal diagnosis or proof about later behavior. No replay/import/execution is performed.
- The existing loader reads current source records; the comparison binds every selected pair to the initial sealed snapshot. Rewrites outside selected comparison time windows that restore identical sealed content are not an authentication claim.
- Text intentionally summarizes gate configuration/counts; JSON preserves the full unchanged gate/history. INVALID discards group/pair diagnosis rather than publishing mixed evidence.
