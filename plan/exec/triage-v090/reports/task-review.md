# Independent task review — core and CLI/package lanes

Reviewed candidate `cb2ab9e9a8db425add30e3a132e005ca2b46d3dc` against base
`16e8a1a`, the two `.superpowers/sdd/PLAN/task-*-brief.md` files, the
`review-16e8a1a..cb2ab9e.diff` package, and both lane reports. This is a
read-only implementation review; only this report was written. No product edits,
Git mutations, network operations, recorded target imports, or subagents.

## FINDINGS

No actionable correctness, specification, or quality findings in either reviewed
lane. No frozen-contract problem identified.

## VERDICTS

| Lane | SPEC | QUALITY |
| --- | --- | --- |
| Task 1: core and additive context helper | ACCEPT | ACCEPT |
| Task 2: CLI and installed-package smoke implementation | ACCEPT | ACCEPT |

These are implementation verdicts for the inspected candidate, not publication
approval or an independently observed fresh-wheel/full-suite pass. The
orchestrator's in-progress integration checks remain required.

## Decisive evidence

### Task 1

- `src/arci/triage.py:96-102` calls `load_run` and pure `decide`, uses fixed safe
  invalid-store reasons, and terminates before selection/comparison on run-level
  ERROR. `:223-229` serializes the complete original `GateDecision`, adding only
  the decision-seal alias. Counts, conditions, statistical configuration, history,
  prior runs, and original seals therefore survive without reconstruction.
- `src/arci/triage.py:104-110` derives observed candidates and stable order from
  the frozen schedule, pairing with schedule `pair_id` identities. The successful
  gate has already checked unique scheduled identities and a valid stopping look
  (`src/arci/gate.py:284-342`); subsequent dictionary lookup does not silently
  accept duplicate records or missing counterpart trials.
- `src/arci/triage.py:113-155` groups only candidate FAIL records by the actual
  `(condition_id, fingerprint)` tuple, distinguishes `None` from every string,
  caps output at three groups, and sorts hard groups first even when ceiling.
  Gating BLOCK then other gating then descriptive ceiling precedence is explicit.
  The representative key at `:117-125` prioritizes actual hard trials, baseline
  PASS, then scheduled order. Counts are separate from explicit pair selection
  (`:156-161`, `:215-217`).
- `src/arci/triage.py:165-198` uses `check_traces` for every selected pair in the
  same directory. Both returned source identities/outcomes/gate states and all
  manifest/trial/decision seals must match the initial snapshot before context
  construction. The decision seal binds the complete initial trial-set digest.
  INVALID comparison or mismatched evidence returns a fresh INVALID result,
  discarding all earlier accumulated groups/pairs/contexts rather than mixing
  evidence. Context reads the initial, hash-matched envelopes.
- `src/arci/trace_check.py:261-305` maps only normalized containing-record
  positions, resolves finish occurrence through the validated matching start,
  and bounds/escapes tool display. It does not evaluate the comparator pointer or
  introduce another equality rule. `src/arci/triage.py:191-196` derives presence
  from non-null comparator digests, preserving JSON-null presence correctly.
- `src/arci/triage.py:79-81` preserves the original gate exit unless diagnostic
  status is INVALID. The renderer exposes metadata, full hashes, the unchanged
  comparator object, and containing-record context without argument/result
  values, raw failure details, or annotations. Fixed limitations explicitly
  constrain causal, reliability, equality, and sanitization claims.
- The added tests exercise hard ceiling priority, hard representative selection,
  real early stops, reversed record order and opaque condition names, distinct
  missing/empty fingerprints, explicit PASS, all source-hash combinations,
  source identity substitution, later-pair store rewriting, incomplete calls,
  null/missing/terminal/absent context, controls, truncation, no writes, and payload
  canaries. These assertions were inspected rather than accepted from the report.

### Task 2

- `src/arci/cli.py:698-710` registers the exact authorized command shape and
  explains statistical versus diagnostic exits and disclosure/causality limits.
  `:868-875` delegates selection, comparison, rendering, and exit policy entirely
  to the shared API. Existing command branches are unchanged in the reviewed diff.
- `tests/unit/cli/test_triage.py:108-145` builds sealed native stores with
  unimportable recorded target names and independently confirms fixture gate
  verdicts. Tests cover help/argument handling, all gate exits, PASS-with-DRIFT,
  invalid selectors/events/stores, source preservation, and summary non-creation.
- `.github/scripts/wheel_smoke.sh:25-27,64-76` clears inherited checkout paths,
  creates/installs into a fresh environment, changes to an empty external working
  directory, and checks installed import provenance. The added invocation at
  `:94-95` runs the helper with that environment's interpreter and `-P`, immediately
  after the unchanged existing trace-check smoke.
- `.github/scripts/triage_smoke.py:190-207` independently requires safe-path mode,
  cleared PYTHONPATH, package provenance inside `sys.prefix`, and external cwd/demo
  paths. `:97-100` invokes actual installed `python -P -m arci triage` subprocesses;
  no checkout import or mocked engine substitutes for the product command.
- `.github/scripts/triage_smoke.py:120-181` compares the entire returned gate to
  the source-derived decision, exact envelope/nested field sets, real source
  seals, original paired outcomes, group counts, and presence from comparator
  hashes. `:209-271` exercises exits 0/1/2/3, diagnostic override with original
  BLOCK/1 retained, explicit PASS selection, ERROR early termination, and synthetic
  PASS/0-with-DRIFT without executing recorded code. Source-byte snapshots and
  summary non-creation are checked at `:239-244,267-274`.

## Independent verification and limits

- Independently compared parsed ASTs of base and candidate
  `src/arci/trace_check.py`: after removing only the additive `json` import,
  `TraceStepContext`, and `trace_step_context`, the ASTs are identical. Command:
  `.venv/bin/python -B -` with stdlib `ast`, read-only `git show`, and an exact
  `ast.dump(..., include_attributes=False)` assertion. Result: exit 0,
  `Comparator AST unchanged after removing additive JSON import/context helper.`
- Read `AGENTS.md`, frozen interfaces/schema/statistical and relevant event,
  schedule/early-stop semantics, trust model, and `plan/exec/CONTRACT.md` before
  evaluating behavior. Current HEAD was confirmed as the reviewed candidate.
- The orchestrator reports 231 targeted tests, repository Ruff, and strict types
  clean. Those are supplied integration evidence, not independently rerun here.
  No redundant full suite was run; fresh-wheel and full-suite evidence are owned
  by the orchestrator and were still running at dispatch.
- The comparator AST check establishes preservation of the existing comparison
  implementation; it does not replace the orchestrator's retained receipt-byte
  verification or the required installed-wheel execution.
- Prior memory was used only to locate the diagnostic/statistical boundary and
  independent-verification cautions; decisive conclusions above use current
  checkout source and requirements.
