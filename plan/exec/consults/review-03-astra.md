REVIEW 03 — Reviewer Astra | Verdict REVISE

Findings by severity:

- **MAJOR — `src/arci/descriptor.py:579`: unordered YAML collections produce nondeterministic manifests.** SafeLoader constructs `!!set`, and Pydantic accepts sets for tuple fields. With `argv: !!set {python: null, "-m": null, mypackage.agent: null}`, hash seed 1 produces `("python", "-m", "mypackage.agent")`; seed 3 produces `("mypackage.agent", "python", "-m")`. The same descriptor changes the executable. Sets in `prior_runs` also change ordering and seals. **Verify:** compile identical text under `PYTHONHASHSEED=1,2,3`; reject unordered collections before tuple coercion.

- **MINOR — `src/arci/descriptor.py:568` and `:479`: malformed values bypass the descriptor error contract.** `task: {x: .nan}` escapes as a hashing `ValueError`; `task: {x: !!bool "WHAT"}` escapes as `KeyError`. The CLI still returns 3 on one line, but omits the descriptor filename and source path; library callers receive exceptions other than the documented `DescriptorError`. **Verify:** exercise both inputs through compilation and CLI error handling, requiring contextual `DescriptorError`/`CliError` diagnostics.

- **MINOR — `src/arci/descriptor.py:504`: union-tag removal can identify the wrong task field.** For `task: {foo: {dict: {}, bad: !!timestamp 2026-10-13}}`, the error reports `task.foo.dict`, although the invalid value is at `task.foo.bad`. The heuristic mistakes Pydantic’s synthetic `dict` tag for an actual dictionary key. This also corrupts error ordering. **Verify:** add nested dictionary/list cases with keys matching union tags and assert the actual offending path.

- **MINOR — `src/arci/descriptor.py:430`: “first by source path” excludes skipped model validators.** A valid descriptor containing both `oracle` and `contract`, plus unknown `zzz`, reports only `zzz`; the earlier `oracle` conflict is never collected because field validation prevents the after-validator from running. Sorting the resulting errors cannot recover it. **Verify:** combine alias conflicts with later unknown keys, reverse their YAML order, and require the earlier conflict consistently.

Required changes (for REVISE/REJECT):

1. Reject unordered collections wherever sequences are required; add command-argument and seal determinism regressions.
2. Convert malformed scalar and unsealable JSON failures into contextual descriptor errors.
3. Map validation paths structurally, distinguishing synthetic tags from user keys.
4. Collect alias conflicts alongside field errors before selecting the first source path.

Follow-ups:

- Confirmed at `e962259`: supplied diff matches the commit; retry seal and full JSON equal the Python builder; global SafeLoader and `contracts.load_contract` remain unchanged; nested unknown keys are rejected; schema bytes match the committed artifact across three hash seeds.
- Validation: `.venv/bin/python -B -c …` with an in-memory commit loader and pytest returned **`53 passed, 7 skipped`**. Ruff format/check passed on all five changed Python modules.
- No files changed. Filesystem/subprocess integration tests and exact-commit basedpyright were not run in this read-only environment. Re-run the full task-03 checks on the corrected commit.