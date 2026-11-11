## Suite experiments (`arci-suite/1`)

- The schedule rule (`build_schedule`), stage rule and `arci.gate.decide` above
  apply to `arci/0.5` only. Suite manifests, rules and decisions use the separate
  frozen suite schema, schedule and `docs/STATISTICS_SUITE.md`. Suite trials remain
  ordinary `TrialSpec` / `TrialEnvelope` records, executed by unchanged `run_trial`;
  their `spec_sha256` remains `arci.schedule.spec_sha256(spec)`.
- Before any trial, rebuild and validate the manifest, its integrity seal, its
  content-derived `suite_experiment_id` and `check_suite_plan`. Print the plan's
  warnings. Validate the contract before creating the store. The store refuses
  an existing run directory, including an empty directory or symlink. Only the
  derived id names its child directory; no unverified id is used as a path.
- Tasks and conditions form a full grid, sorted by task id then condition id.
  `build_suite_round` supplies both ordinary specs for every cell of the round;
  both arms share the seed. Never derive trial identity independently. Seed and
  arm order use the frozen sha256-v1 derivation. `fixed` repeats a cell's seed;
  `per_round` includes the round in the seed. Arm order always includes the round.
- A worker slot executes one pair: both arms back to back in `arm_order`, each in
  its own fresh trial process. Pairs can run concurrently across worker slots.
  The canonical storage order is cell order, baseline then candidate, regardless
  of execution order. Events within each trial retain their sequence order.
- A stage is exactly one round. Submit every pair, wait for all pairs, append
  events and trials in schedule order, then call `evaluate_rounds` on the complete
  prefix. Stop at the first non-INCONCLUSIVE round, including ERROR, or at the
  registered cap. No other statistical look, trial retry, rescheduling after
  error, extension of the cap, or resume is supported. Seal and persist the final
  `decide_suite` decision.
- Normal rounds buffer events and envelopes in the parent until the stage finishes.
  The store preserves previous round bytes and publishes each round using an atomic
  replacement of each complete JSONL file. Re-publishing the same round after a
  handled interruption is idempotent; a completed round's trial lines cannot be
  left partly appended. The two files are not one transaction.
- A handled interruption is a Python BaseException during pair submission, waiting
  for results, or publishing a round (including KeyboardInterrupt). Cancel queued
  work, let already active pairs finish both arms, wait for the executor, then save
  every completed envelope and all observed events in schedule order. A worker
  exception stops its own pair and prevents queued pairs from starting. Events
  from a trial that never returned an envelope are retained in events.jsonl too.
  No final decision is written on this path. An abrupt process kill or persistent
  storage failure can lose buffered evidence or leave the two files inconsistent.
  The gate returns ERROR for an empty store, partial round, or inconclusive stop
  before the cap; a fully saved decisive round can still be recomputed without a
  stored decision. There is no resume.
- An errored pair is retained unchanged and never retried. Through the registered
  tolerance, the gate scores it as -1 for PASS wealth and +1 for BLOCK wealth.
  Neither discarding it nor recording it as an observed zero is allowed.
- At each whole round end priority is: errored pairs above tolerance -> ERROR;
  candidate hard violation -> BLOCK; both wealths crossed -> ERROR; PASS crossed
  -> PASS; BLOCK crossed -> BLOCK; otherwise INCONCLUSIVE. Error tolerance is
  cumulative. Candidate hard-violation entries count even on errored trials.
  The false-BLOCK guarantee applies to statistical BLOCK, not the invariant rule.
- Suite descriptors use `suite_id`, flat `tasks: [{id, ...task fields}]` (or a
  JSON/YAML/JSONL task file relative to the descriptor), and the existing v1 arm,
  toolset/MCP, oracle/contract and explicit condition/fault syntax. Conditions
  are preserved as declared, as in v1: no implicit clean condition is inserted.
  `rule` contains the exact rational rule and explicit budgets after defaults.
  Decimal rule values are converted from their written spelling without binary
  floating-point rounding; overlong exact fractions are refused. Duplicate JSONL
  task keys and explicit null budgets are refused. JSON task files use the JSON
  parser (including exponent numbers and surrogate-pair escapes); YAML uses the
  descriptor YAML parser. JSON/JSONL refuse duplicate keys and non-finite constants.
  Task files accept a UTF-8 BOM. JSONL splits only on newline and reports the file
  line number on parse errors; Unicode separators inside JSON strings are data.
- On descriptor execution, inspect immediate child directories of the output root
  in sorted order. Inspect manifest schema_version first; skip v1 manifests without
  suite validation and directories with neither a manifest nor trials. Warn with
  the manifest path and skip unreadable, malformed, unsealed or invalid suite
  manifests, unsupported versions, and trial directories missing their manifest.
  Skipped history is not recoverable automatically. For valid suites, match suite_id
  and a nonempty candidate_id; when the new candidate_id is empty compare agent and
  command, ignoring label. Preserve explicit prior_runs, then append each matching
  manifest's own prior_runs and experiment_id without duplicates before sealing.
  Even a manifest-only directory counts. Sealed-manifest execution never changes
  its prior-run list. A new run is a new campaign outside the single-experiment
  bound; listing predecessors does not supply cross-run error control.
- Dispatch suite stores and sealed manifests by explicit schema_version. Descriptor
  dispatch uses tasks/suite_id without experiment_id; a v1 descriptor with stray
  suite keys reports those keys and how to remove them or convert the descriptor.
  Suite sniffing never reads non-regular files or regular files aliased to stdin,
  preserving v1 run/replay inputs such as /dev/stdin.
- Suite `arci run` accepts a descriptor or sealed SuiteManifest JSON, honours
  --workers as the number of concurrent pair slots, prints the suite summary and
  store path, and exits PASS=0, BLOCK=1, INCONCLUSIVE=2 or ERROR=3. Descriptor paths
  discover history before sealing; sealed manifests are validated without edits.
- Suite `arci gate` is a recomputation and comparison: missing saved decisions
  are reported as absent; malformed, unsealed or unequal saved decisions give
  exit 3, and saved decisions are never replaced. Output includes reasons,
  stopping round, pair counts, both displayed wealths and exact crossing flags,
  threshold, error tolerance and the sealed seed mode's qualified guarantee.
  Wealth display strings never decide a crossing. `gate --markdown` exports this
  summary; --junit exits 3 with one line saying JUnit export for suites is not
  built yet, without reporting a store-validation failure. Both run and gate print
  the seed-mode guarantee qualified by the frozen statistics document; per_round
  includes its per-round-null condition in the same sentence.
- `report`, `triage`, `diff`, `minimize`, `bundle`, `replay`, `trace-check` and
  `plan` refuse suite inputs with exit 3 and the one-line message
  `suite support for <command> is not built yet`. Dispatch uses parsed inputs,
  including abbreviated options; output paths are not inputs. Their v1 routes remain intact.
- The packaged `arci.demo.suite` fixture has five tasks by four conditions,
  seeded control/regression/uncertain agents, and no model call. Every agent's
  success depends on a uniform eight-way draw from the trial RNG: success rates
  are 7/8, 1/8 and 6/8 respectively in each cell. The shared paired draw makes the
  control identical to baseline and gives mean regressions of 3/4 and 1/8.
  Retrying the injected one-shot tool fault does not change this draw. Its seed
  mode is per_round. Tests enumerate the paired laws (minus, zero, plus) with
  operating_characteristics at the four-round cap and require PASS, BLOCK and
  INCONCLUSIVE probability respectively at least 0.999. These are projections
  under independent uniform draws, not evidence of provider independence or a
  guarantee averaged over deterministic hash-derived seeds.
