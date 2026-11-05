# Independent whole-branch review

Reviewed base `f039e1ddd07011a6018b88171cb51d5be3d63b26` through candidate
`d11476945d449cceb84bb7204dccabcc14e62543`. The immutable package's diff section
matches `git diff -U10 f039e1d..d114769` exactly. Review covered the production,
test, installed-smoke, documentation, compatibility and packaging changes against
the approved plan and its v1.0.0 amendment. The checkout remained on the candidate;
only this report was written. No source/index/Git-state changes, network access,
recorded target execution or subagents were used.

## Strengths

- `src/arci/triage.py:96-110` derives the whole-run gate before selecting observed
  scheduled candidates. The gate already rejects duplicate/missing identities and
  invalid stopping histories. `:223-229` serializes that original decision in full,
  preserving condition counts, configuration, prior runs, reached looks and seals.
  `:79-81` overrides its exit only for invalid diagnosis. No alternative statistical
  rule is introduced.
- `src/arci/triage.py:113-161` keeps absent fingerprints distinct from real strings,
  sorts hard-violation groups ahead of gating BLOCK and descriptive ceiling groups,
  and selects an actual hard-violating representative before baseline-PASS and
  schedule-order preferences. Explicit candidate selection changes the selected
  pair without redefining failure-group counts or experiment denominators.
- `src/arci/triage.py:165-198` binds both comparator sources to the initial manifest,
  selected trial, complete decision seal, identity, outcome and gate state before
  producing context. A later invalid pair discards earlier accumulated diagnoses.
  The decision seal also binds the complete trial-set digest.
- `src/arci/trace_check.py:261-305` adds only containing-record context. It follows
  the existing normalized projection, resolves finish occurrences through their
  starts, and bounds/escapes displayed tool names. Presence derives from comparator
  hashes at `src/arci/triage.py:191-196`, so JSON null remains present and a missing
  field does not invent an absent event. The equality engine is unchanged.
- `src/arci/cli.py:698-710` and `:868-875` expose a thin shared-API command with the
  documented exit meanings. The source path contains no target import, runner,
  replay, store write or Step Summary write. New core/CLI tests cover selection,
  early stopping, ceiling hard violations, null/missing contexts, source changes,
  error precedence, escaping, payload canaries and source immutability.
- `.github/scripts/triage_smoke.py:190-207` verifies safe-path mode, cleared import
  paths, installed package provenance and execution outside the checkout. Its real
  CLI subprocess assertions cover exact JSON structure, full gate equality,
  PASS/BLOCK/INCONCLUSIVE/ERROR, invalid diagnosis, explicit PASS, PASS-with-DRIFT,
  source hashes and no summary writes. The prior trace-check smoke remains intact.
- `docs/COMPATIBILITY.md:3-18` states a concrete CLI/format compatibility policy,
  distinguishes presentation from machine output, and retains frozen-interface
  authority. `:22-36` preserves statistical/diagnostic, integrity/authentication,
  replay/live-inference and POSIX/runtime boundaries.
- The recipe and README describe native decision diagnosis without superiority or
  causal claims. `plan/exec/triage-v090/rehearsal/REPORT.md:3-8,28-36` preserves the
  non-blinded agent-QA scope, excluded setup time, original unpublished 0.9.0 wheel
  provenance and single-fixture timing limitation. The release-direction report
  acknowledges overlap and treats 1.0.0 as a compatibility commitment.

## Findings

### Critical

None.

### Important

None.

### Minor

None.

## Independent verification

Read AGENTS, frozen interfaces/schema/statistics, relevant event and sequential
semantics, trust model, execution contract, approved plan, progress, task review,
release-direction report and rehearsal evidence before judging the implementation.

Read-only `.venv/bin/python -B -` probes independently established:

- All 54 current FROZEN hashes validate. The only changed pre-existing entries
  are `pyproject.toml` and `uv.lock`; the sole added entry is the approved release
  design record. All 272 baseline protected-file hashes remain unchanged.
- Parsed TOML is identical to the base after normalizing only the project/root
  package version. Dependency versions, hashes, markers and sources are unchanged.
- Removing only the additive `json` import, `TraceStepContext` and
  `trace_step_context` leaves an AST identical to the base comparator.
- The first 120 README lines are unchanged; the first changed line is 123.
- Both retained triage JSON receipts reproduce byte for byte: retry BLOCK/1 and
  repeat INCONCLUSIVE/2. Retry text also reproduces exactly. All eight rehearsal
  source hashes match both retained manifests before and after these reads.

`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B
plan/exec/trace-check/rehearsal-2026-11-03/verify.py` independently returned:

```text
case-1: DRIFT/1, receipt matches
case-2: DRIFT/1, receipt matches
case-3: MATCH/0, receipt matches
All 29 source-file hashes unchanged
```

`git diff --check f039e1d..d114769` passed. Initial review-probe assertions assumed
an unwrapped default-context diff; the package has a commit header and ten context
lines. The corrected probe verified the exact diff section. These were reviewer
probe corrections, not candidate failures.

The orchestrator supplied 231 focused passes, an earlier 1404-test full pass,
format/lint/types checks and fresh installed-1.0.0 smoke results. Before this
report closed, it additionally reported the final-version full suite completed
with 1404 passed in 423.88 seconds and exit 0, with no intervening production/test
changes. Those suites and wheel installation were not rerun in this read-only
review. Hosted PR CI and a rebuilt-wheel full smoke were still running; no success
for either is inferred here.

The unchanged `Development Status :: 4 - Beta` classifier at `pyproject.toml:12`
does not invalidate the explicit 1.x compatibility commitment. Package maturity
and compatibility policy are separate claims, and `docs/COMPATIBILITY.md:3-6`
already avoids a production-maturity claim. Preserve the approved version-only
frozen change; mentioning the retained classifier in release wording is reasonable
clarity, not a reason to broaden metadata changes or assert greater maturity.

## Declined to judge

- Human adoption, retention, production safety, general diagnostic accuracy and
  market superiority: intentionally outside the approved fixture/agent-QA scope;
  the release makes none of these claims.
- Exhaustive competitor coverage or future popularity: outside the bounded overlap
  review. I inspected its local synthesis and resulting product wording, but did
  not independently re-fetch external sources under this seat's no-network rule.

## Verdict

**ACCEPT** the inspected candidate diff. No actionable correctness, compatibility,
frozen-boundary, dependency or public-claim issue was identified.

Release decision remains pending the approved exact-candidate checks, exact-main
CI, tag/release workflow, published-byte comparison and clean downloaded-artifact
verification. Release-ready availability prose is not evidence that publication
has happened. This review does not waive those gates or claim a hosted/released
artifact was inspected. Browser rendering was not evaluated in this source review.

Prior memory informed only the diagnostic/statistical boundary and evidence-label
cautions; all decisive implementation and preservation conclusions above were
checked against this candidate and its retained artifacts.
