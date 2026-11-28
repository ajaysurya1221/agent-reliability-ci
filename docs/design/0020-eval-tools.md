# 0020: ARCI on top of five evaluation tools

Record by the orchestrator, 2026-11-28. Decision D-41 in `plan/exec/v2/DECISIONS.md` on the
branch `v2/phase0`: the maintainer chose that ARCI works on top of promptfoo, DeepEval, Opik,
MLflow and Langfuse, approved the plan, chose "recipe + reader" as the depth and "no servers",
and holds the release. This record extends 0019 (`arci check-change`) without changing it. The
facts about the five tools below come from their real outputs in
`tests/unit/integrations/real/` (README there), made on 2026-11-28 with the versions named.
Nobody outside the project has asked for these connections.

## Why

The five tools run tests of prompts and agents and are widely used. ARCI adds one thing on top
of them: a verdict from a rule fixed before fresh paired runs, with a margin of allowed loss,
read after every round, that may be "cannot tell". Two of the tools have statistics of their
own, and every page must say so: MLflow 3.18 has an experimental paired
comparison of two runs (`mlflow.genai.compare_evaluations`), and promptfoo writes per-test
pass-rate ranges with `--repeat` (`results.repeatStability`). The aim is that a user of any of
the five can get ARCI's verdict on a change with the tests they already have.

## Decision

### The rule: convert, never rename

A sealed decision names only the four formats of 0015 (`outcome_schema.py`, frozen). A result
file of another tool is therefore converted into ARCI's neutral JSONL rows by a reader, and
everything ARCI seals refers to that JSONL. `check-change` keeps and verifies both the original
and the converted file; `convert` writes only its output file, which carries the source digest
in every row. A manual `arci verdict` on converted files does not check any original. Each
converted row carries, besides `task_id` and `outcome` (and `round` where stated),
two fields the released reader ignores (0015: "nothing else is read"): `source_sha256`, the
SHA-256 of the original file's bytes, and `reader`, the reader's name and version
(`promptfoo/1`). For a given original and given selectors the output bytes are fixed: JSON is
parsed with duplicate keys and lone surrogates refused, an integer token becomes a Python `int`,
a fraction or exponent token a finite float; each output line is
`arci.hashing.canonical_json(row) + b"\n"`, with the rows in source order.

### promptfoo reader (`src/arci/importers/promptfoo.py`, new)

Input: one promptfoo JSON output file (`-o FILE.json`), results `version: 3`. Its JSONL, CSV,
HTML and JUnit outputs are not read (its JUnit ids number the rows and cannot be paired).

- **Cell.** A file holds one or more cells; a cell is one `promptIdx` with one
  `provider.label` (the provider `id` when there is no label). The reader reads exactly one
  cell. A file with more than one cell is refused unless the caller selects one with
  `prompt=N` (a `promptIdx`) and/or `provider=LABEL` (with both, a cell must match both); a
  selection that matches no cell or more
  than one is refused, and the message lists the cells.
- **Task id.** `D` is `testCase.description`: null when absent or null, otherwise the exact
  string (the empty string stays empty). `V` is `testCase.vars`: `{}` when absent or null,
  otherwise an object (anything else is refused). The id is the first 80 Unicode code points of
  `D or "test"`, then `" #"`, then the first 16 characters of
  `arci.hashing.hash_record({"description": D, "vars": V})` (frozen; canonical JSON: keys
  sorted, no whitespace, UTF-8, no ASCII escaping). An ` #` inside the description is kept.
  Golden vector: description `Row #1`, vars `{"x": [1, 1.0, true, null, ["é"]]}` gives
  `Row #1 #25722901d99dfa75`.
- **Outcome.** `error` when `failureReason` is 2; otherwise `pass` when `success` is true and
  `fail` when it is false.
- **Round.** Without repeats (`repeatIndex` null or absent in every row of the cell, and
  `runtimeOptions.repeat` 1 or absent) the rows carry no `round`. With repeats every row carries
  `round = repeatIndex + 1`, and the number of rounds must equal `runtimeOptions.repeat`. A cell
  where some rows have a `repeatIndex` and others do not is refused.
- **Types.** `promptIdx`, `repeatIndex` and `failureReason` must be JSON integers (a boolean is
  not an integer); `success` must be a boolean; an HTTP status counts when it is an integer, or a
  number with an integral value (`500.0` counts as 500).
- **Refused, with a fixed message naming the reason:** not a JSON object; results `version`
  other than 3; a row without `testCase`; a `testCase.vars` that is neither absent, null nor an
  object; `success` not a boolean; `failureReason` not 0, 1 or 2, or contradicting `success` (0 with false, 1 or 2 with
  true); a recount of the whole file (all cells) that differs from `results.stats.successes`,
  `failures` or `errors`; any cache use the file reports (`results.stats.cacheHits` above 0, any
  row with `response.cached` true, or any `results.prompts[].metrics.testCacheHitCount` above 0);
  two rows with the same id in the same round of the cell; repeats where the rounds of the cell
  do not hold the same set of ids; a `repeatIndex` that is not a whole number from 0; rounds
  that are not 1 to N without gaps; any row whose `response.metadata.http.status` is an integer
  from 400 to 599 (promptfoo can stop a run on such an answer and still write a file).
- **Cache use the file reports**, each refused on its own: `results.stats.cacheHits` above 0;
  any row with `response.cached` true; any `results.prompts[].metrics.testCacheHitCount` above
  0; `results.repeatStability.cachedResults` above 0; any `results.repeatStability.groups[]`
  with `cached` above 0 (an integer count; `true` is treated as 1); `metadata.cachedResponse` true on any `gradingResult` or nested
  `componentResults` entry. Absent counters and an absent `response.cached` (a `file://`
  provider writes none) are accepted.
- **Also returned:** the cache setting `runtimeOptions.cache` (true, false or absent), the tool version (`metadata.promptfooVersion`, or null), the run id
  (`evalId`) and the run time (`results.timestamp`), for the checks in `check-change`.
- Tested tool versions: 0.125.1 and 0.126.0. Another version is read, and the caller prints one
  notice line saying the reader was not tested with it.

### `arci convert` (`src/arci/convert.py`, new; one sub-parser in `cli.py`)

```text
arci convert --from promptfoo SOURCE.json --out OUT.jsonl [--prompt N] [--provider LABEL]
```

- Reads one source, writes one file. `OUT` must end in `.jsonl`, must not exist, must not be
  `SOURCE`, and its folder must exist. The file is written only after the whole conversion has
  succeeded, created exclusively; a refusal writes nothing.
- Prints: the reader, the tool version, the source digest, the selected cell, rows, rounds,
  counts of pass, fail and error, and the fixed sentence: "These are existing results: use
  `arci verdict-rule` and `arci verdict` for a descriptive verdict; the error bound needs fresh
  runs (`arci check-change`)."
- Exit status: 0 written; 3 refused or unreadable. No other status.
- When `runtimeOptions.cache` is true and no cache use is reported, `convert` writes the file
  and prints a notice that the cache was on, so answers may come from earlier runs that the file
  cannot show.
- `convert` has its own messages and does not go through the fixed E-codes of 0015.
- A run that holds both versions as two prompts (or two providers) is split by running `convert`
  twice with different selectors.

### `check-change --format promptfoo` (extends 0019)

- `{out}` is replaced by a path ending in `.json` (promptfoo chooses its output format by
  extension). The original is kept as `round-NNN/{arm}.json` (`discovery/baseline.json`).
- The snapshot is the conversion of the captured original bytes, written exclusively as
  `round-NNN/{arm}.snapshot.jsonl`. Two digests are held in memory: the original's and the
  snapshot's. Both files are checked against them where 0019 checks one.
- `fmt="jsonl"` is passed to discovery and to every assessment; each sealed decision's input
  digest is verified against the snapshot's. Campaign snapshots carry no `round` field, so the
  position of a file assigns its round, as for JUnit in 0019. A manual replay must list the
  snapshots in numeric round order (`round-100` after `round-099`; a shell glob sorts
  `round-1000` before `round-101`): `arci verdict rule.yaml --baseline round-001/baseline.snapshot.jsonl
  round-002/baseline.snapshot.jsonl ... --candidate ...` reproduces the counts, the stopping
  round and the exit status. The file index the command prints is in that order.
- `arci convert --from promptfoo` on a kept original reproduces its snapshot byte for byte.
- ARCI sets `PROMPTFOO_FAILED_TEST_EXIT_CODE=100` in the launch's process environment,
  overriding the caller's value. A promptfoo suite file can still override it; exit status 1 is
  refused even when a configured test failure produced it. Accepted exit
  statuses: 0 and 100; the raw status is recorded. Every other status, including 1 (promptfoo's
  status for any other error), ends the campaign with ERROR, as in 0019. Because promptfoo also
  exits 100 when the target failed, the file is always validated, and the HTTP-status refusal
  above applies.
- The cache must be off in a way the file shows: `runtimeOptions.cache` must be false (promptfoo's
  `--no-cache`). `PROMPTFOO_CACHE_ENABLED=false` does not show in the file (it still records
  `cache: true`), so a file with `cache: true` ends the campaign with ERROR and the message names
  `--no-cache`.
- In addition to 0019's checks, each of these ends the campaign with ERROR and starts no further
  launch: a file with repeats; any cache use the file reports; `runtimeOptions.cache` that is
  not the literal `false` (true, null or absent); an empty or missing `evalId`,
  `results.timestamp` or tool version; more than one cell; a run id
  (`evalId`) seen before anywhere in the campaign; a run time (`results.timestamp`) that denotes
  the same instant as an earlier file of the same side (compared as in 0019); a tool version different from the one discovery saw; any
  reader refusal.
- `plan.json` gains, for this format only, `reader` (`promptfoo/1`), `scored_format` (`jsonl`)
  and `tool_version` (from discovery). For `junit`, `csv` and `jsonl` it is unchanged.
- After the released verdict block one line is printed: "Results from promptfoo VERSION, read by
  promptfoo/1. To check one: arci convert --from promptfoo round-001/baseline.json --out
  check.jsonl". A version outside the tested list adds the notice line.

### DeepEval, Opik, MLflow and Langfuse: recipes, no new ARCI code

- **DeepEval** (`docs/recipes/deepeval.md`): `deepeval test run TESTS --junitxml={out}` as the
  test command of `check-change` (format `junit`, the default). Parametrize with explicit,
  stable `ids=[...]`; a positional id (`golden0`) pairs by position, not by task.
- **Opik** (`docs/recipes/opik.md`): `pytest TESTS --junitxml={out}` with `@opik.llm_unit()` and
  `OPIK_PYTEST_EXPERIMENT_ENABLED=false`. Without that variable Opik sends results to its cloud
  address by default; the page says so. The real files were made with both
  `OPIK_PYTEST_EXPERIMENT_ENABLED=false` and `OPIK_TRACK_DISABLE=true` (the second stops
  `@opik.track` from trying to send traces), and the page shows that combination only. Opik's own report needs an Opik server and is
  not used.
- **MLflow** (`docs/recipes/mlflow.md`): the user's evaluation script calls
  `mlflow.genai.evaluate` and then writes ARCI's neutral JSONL to `{out}` with
  `examples/integrations/mlflow_rows.py`, copied into the page verbatim. Mapping per row of
  `result_df`: `error` when `state` is not `OK` (a crashed `predict_fn`: MLflow still scores the
  empty answer as false) or `<scorer>/error_message` is set; otherwise `pass` when
  `<scorer>/value` is true or `"yes"`, `fail` when false or `"no"`, `error` for any other value.
  The task id is a function of `request` the user gives. The page names
  `mlflow.genai.compare_evaluations` and how ARCI differs from it.
- **Langfuse** (`docs/recipes/langfuse.md`): the user's script calls `run_experiment` and then
  writes neutral JSONL with `examples/integrations/langfuse_rows.py`, copied into the page
  verbatim. Every expected task id gets a row: an id missing from `item_results` (its task
  raised; Langfuse drops it) is `error`; an item without the named evaluation (its evaluator
  raised) is `error`; otherwise `pass` for true or 1, `fail` for false or 0, `error` for any
  other value. The page says it was tested with the SDK's `run_experiment` and tracing off, not
  against a live Langfuse.
- The two helper files use the standard library only, are fully typed, import neither MLflow
  nor Langfuse, and are covered by ruff and basedpyright like the rest of `examples/`. The MLflow
  helper takes the records of `result_df.to_dict("records")`; the Langfuse helper takes the SDK's
  result objects by attribute (`item`, `evaluations`, each evaluation's `name` and `value`). Both
  refuse duplicate task ids; the Langfuse helper refuses an item with two evaluations of the
  requested name. In MLflow a missing, null or NaN `<scorer>/error_message` means no error;
  only exact `True`, `False`, `"yes"` and `"no"` are scores (`1`, `0` and `"True"` are `error`).
- **Faults count as failures in two routes**, and the pages say so: under pytest an exception in
  the test body is a JUnit failure (DeepEval, Opik), and a promptfoo assertion that throws is a
  failed assertion. An infrastructure fault there is scored as a worse answer, which the error
  bound does not distinguish; the pages show how to mark a broken set-up as skipped (an error
  in ARCI).
- **Index** (`docs/recipes/eval-tools.md`): one table: tool, version tested, route, how it was
  tested, what to watch for. One entry under "Unreleased" in `CHANGELOG.md`.

## Acceptance items

All offline. Real files only from `tests/unit/integrations/real/` (and, for promptfoo 0.125.1,
`tests/unit/outcomes/real/promptfoo/`). A test may derive a copy of a named real file by
changing named fields only (`evalId`, `results.timestamp`, and a row's `success` with its
`failureReason` and `results.stats` kept consistent); the derivation is code in the test. "Recomputed" means computed in the test from the raw
file by code that does not call the code under test.

**A. promptfoo**
1. For every real promptfoo JSON file the reader accepts (all but `shapes.json` and
   `cache-warm.json`; `two-prompts.json` and `two-providers.json` with a selector), the reader's
   rows equal the recomputed rows, and the recount equals `results.stats`.
2. Ids are equal across `words-baseline`, `words-candidate`, `words-single` and the three
   0.125.1 files, and across all repeats; reordering the rows or the keys of `vars` in a copy
   changes no id.
3. Each refusal listed for the reader, and each of the six cache signals, is tested one by one
   on a copy of a real file edited in that one place (including the real `shapes.json` for
   duplicate ids, the real `cache-warm.json`, a `repeatStability` group with `cached: 2` as the
   only signal, `testCase.vars` null giving the same id as absent, and booleans in place of
   integers); `cache-cold.json` and `cache-env-off.json` are
   accepted by `convert` with the cache notice. The golden vector gives its id.
4. `convert` writes exactly one file, the same bytes on every run; each refusal (reader and
   path rules) exits 3 and leaves no new file, and a file that already existed at `OUT` keeps
   its bytes.
5. `verdict-rule` and `verdict` on `convert` outputs of `words-baseline` and `words-candidate`
   give the pair counts recomputed from the raw files, with the descriptive statement.
6. `two-prompts.json` converted with `--prompt 0` and `--prompt 1`, and `two-providers.json`
   with `--provider old` and `--provider new`: every `(round, id, outcome)` of each output equals
   the source rows filtered independently by that cell; rounds are 1 to 3; id sets are equal
   between the two cells. Without a selector both files are refused and the message lists the
   cells; a selector that matches no cell, one that matches two, and `--prompt 0 --provider new`
   on `two-providers.json` (each option matches a different cell) are refused.
7. `check-change --format promptfoo` with a fake command that copies a real file to `{out}`:
   decisions name `*.snapshot.jsonl` with the format `jsonl`; `arci verdict` by hand on the
   snapshots, listed in numeric round order, reproduces counts, stopping round and exit status,
   checked at round 2 and with its predecessor decision (derived copies: round 1 ties, round 2
   losses, each launch a fresh `evalId` and run time); the fake command sees
   `PROMPTFOO_FAILED_TEST_EXIT_CODE=100` in its environment.
8. `convert` on each kept original reproduces its snapshot byte for byte, and every row's
   `source_sha256` equals the original's digest.
9. `plan.json` is unchanged for `junit`, `csv` and `jsonl`, and has the three added keys for
   `promptfoo`.
10. Each of these gives exit 3, keeps the files written so far and starts no further launch: a
    changed original; a changed snapshot; a reused `evalId`; a reused run time on one side; a
    file with repeats; a file with cache use; a file with two cells; a changed tool version; a
    reader refusal; a file with `runtimeOptions.cache` true, null or absent; an empty `evalId`,
    run time or tool version; a row with HTTP status 500 and one with 500.0; a launch exit
    status of 1.
11. With `e2e-discovery.json`, `e2e-r1-baseline.json` and `e2e-r1-candidate.json` served by the
    fake command: BLOCK at round 1, exit 1. Serving the same file twice gives exit 3. A launch
    exiting with 100 and a valid file is accepted.
12. The existing tests pass unmodified; `shasum -a 256 -c FROZEN.sha256` passes; ruff and
    basedpyright are clean on every changed file.

**B. DeepEval and Opik**
1. Every real DeepEval and Opik JUnit file read by the released JUnit reader gives the rows
   recomputed from the raw XML (failure is `fail`, skipped is `error`, an exception in the test
   body is `fail`).
2. The ids of `e2e-r1-baseline.xml` and `named-run2.xml` are equal (explicit ids); the
   positional ids in `deepeval/shapes.xml` are `[golden0]` to `[golden2]`.
3. Every real file has a suite `timestamp`, and the timestamps of different runs differ.
4. `check-change` (format `junit`) with a fake command serving the three `e2e-*.xml` files of a
   tool: BLOCK at round 1, exit 1; then `arci verdict` by hand reproduces it.

**C. MLflow and Langfuse**
1. `mlflow_rows.py` on the records of `result_df-pass.json` and `result_df-fail.json` gives the
   rows recomputed from the raw JSON; `w07` is `error` (state ERROR) and `w13` is `error`
   (scorer error), each asserted on its own; the output is accepted by `arci verdict-rule` and
   `arci verdict`. Missing, null and NaN error messages, the exact score values and a duplicate
   task id are tested one by one.
2. `langfuse_rows.py` on attribute-shaped objects built from `item_results-pass.json` and
   `item_results-fail.json`, with the 20 expected ids, gives 20 rows: `task-w07` `error`
   (missing), `task-w13` `error` (no evaluation), each asserted on its own, the rest pass or fail
   as recomputed. A duplicate id and two evaluations of the requested name are refused.

**D. Documents**
1. Every tool version named on a recipe page equals the version in the README of the real files.
2. Every command line shown on a recipe page appears in the generator scripts kept with the real
   files, or in a test that runs it.
3. Each recipe page states how it was tested; the MLflow page names `compare_evaluations`; the
   promptfoo page names `repeatStability`; the Opik page names the cloud default; the
   `mlflow_rows.py` and `langfuse_rows.py` code blocks on the pages are byte-identical to the
   files.

## What may and must not be said

May, after the acceptance items pass: that ARCI converts promptfoo's JSON output; that it reads
the pytest JUnit files of DeepEval and Opik; that the recipes include example exporters for
MLflow and Langfuse; each with the versions named and the way it was tested. Must not: "first", "only" or any claim of novelty; "works with all five"
without how each was tested; that these tools have no statistics; that ARCI detects cached
answers in general (only the cache use promptfoo's own file reports); anything about real agents
or hosted models from these fixtures; that anyone outside the project uses it.

## Not in this record

A reader for Opik's own report and any Opik or Langfuse server; MLflow or Langfuse code inside
`src/arci`; promptfoo's JSONL, CSV and JUnit outputs; MLflow's pytest plugin; scores between 0
and 1; the size of a change with a range; a skill; a pull-request comment; any README change and
any release.
