# Size-0 operator interface

Run commands from this directory. The repository-relative agent interpreter is
`../.arci-worktrees/run4-env/bin/python`. The launcher uses that environment read-only,
with Python 3.13.12, released ARCI 2.4.1 and the Run 6 package versions checked in
`freeze.py`. Repository development tools come from the repository's `.venv/bin/`.

## Operator commands

Run the shell wrapper from this directory. Prepare and publish the registration before the first
preflight. Copy `models.example.json` to `models.json` and supply the installed server version
under `ollama` and four records under `slots`. Use the exact installed tag, lowercase full build
digest and the strings reported by Ollama for family, parameter size, format and quantization.
Set each context to 32768. The digest inventory includes `slots.json`. Its inclusive ranges
in billions are 1.5–3.0 for q2, 3.0–6.0 for q4, 7.0–11.0 for q9 and 10.0–14.0 for g12.
The first three families must contain `qwen` (case-insensitive) and share one quantization level.
The g12 family must contain `gemma`. The sample contains synthetic identities. The orchestrator supplies
`PREREGISTRATION-size-0.draft.md`.

| Command | Result |
| --- | --- |
| `sh run-size0.sh list` | All 14 names, remaining starts per day and a serial time-budget estimate through the last start. |
| `sh run-size0.sh digests` | SHA-256 inventory of code, registration, roster, tasks and wire template. |
| `sh run-size0.sh prepare` | Compile 14 descriptors and freeze 2,240 assignment-specific expected first-body digests. Repeat preparation only before a suite has started. |
| `sh run-size0.sh check` | Verify the pushed registration and regenerate the descriptors and assignments locally. |
| `sh run-size0.sh preflight q2` | Run five native streaming probes of a non-study pebble reader. Repeat for each slot before its suites. |
| `sh run-size0.sh real size0-d1-q2-clean` | Admit and permanently claim the named run, then execute released ARCI with one worker. |
| `sh run-size0.sh report` | Verify the current claims, print all 14 statuses and render daily tables from verified claims. |
| `../../../../../.venv/bin/python -B check_evidence.py DIR [--claims CLAIMDIR]` | Use this trusted checker, its local registration Git objects and the pinned compiler/gate to verify an evidence checkout and its claims. |
| `sh check-offline.sh` | Eight released suites with an in-process HTTPX stand-in, four pair workers, synthetic preflight records and two simulated dates. |
| `sh tests/native-rehearsal.sh --production` | Eight native streaming suites, followed by production admission and worker cleanup in a disposable checkout. Requires an unused port 11434. |

Publish the sources and all of `prepared/` with the completed registration and roster. The
operator writes a one-line `push-receipt.txt` containing `<40-hex-commit> refs/heads/v2/phase0`
in `/private/var/tmp/arci-size0-claims`. The local `refs/remotes/origin/v2/phase0` must contain
that commit. Admission compares the working files byte for byte with its Git blobs and recompiles
every descriptor. The wrapper rejects bytecode caches. Workers execute a read-only copy of the
registered agent files, descriptor and assignments. Admission checks the resolved agent, tools
and oracle imports using the released worker's Python path. Bytecode writes are disabled.

Claims and the Size-0 suite lock live in the host claims directory. The wrapper unsets
`SIZE0_CLAIMS` for real execution. Real preflight and execution also lock Board-0's existing
suite lock read-only and check its recorded launcher and process groups. A live ARCI runner or
worker in a registered Board group blocks admission even after its launcher and parent exit. Preflight observes
version, installed and loaded build digests, template SHA-256, parameter size, family, format,
quantization and configured and loaded context. Each probe records native call parsing,
whether the answer repeated the random 24-hex token from the tool result, thinking text
presence and elapsed seconds. Preflight saves every attempt in `preflights/REGISTRATION/SLOT/`, including interrupted attempts.
Admission requires the latest attempt to qualify. Each attempt records whether its first probe was cold.
A parser failure after a completed exchange from the registered model records `native_call=false`
and `parser_error=true`. A wrong responder or incomplete probe cannot qualify.
Each probe takes its load duration from the first HTTP response. If that response omits
`load_duration`, the probe records wall-clock seconds from send through end of stream and sets
`load_duration_missing` to true. The attempt also records this flag for its first probe. The cold-load field uses that
probe when the tag was initially unloaded. A slot can qualify with zero parsed
tool calls. Run preflight again when necessary to load the slot before admission. Its identity
must agree with earlier preflight evidence, the roster and both suite observations.

The first claim of each nominal day fixes the local date and UTC offset for all runs of that day.
Day 1 runs q2, q4, q9, g12. Day 2 runs q9, q4, q2 on a later date. Each slot runs clean then
null. A suite may finish after local midnight. If any remaining start for that nominal day would
cross local midnight, the day stays partial. The time estimate from `list` is meaningful only between suites. It budgets 160 serial trials
per preceding suite and 120 seconds plus 20 grading seconds per trial. Allow additional time
for setup, model loading and time between starts. A date refusal leaves the run unstarted. A claim consumes the only start even if a process
dies. A missing or unfinished predecessor blocks admission. A shortened store must contain
an exact, nonempty scheduled prefix of whole rounds and a replayed decision at the end of that
prefix. The errored-pair stop uses the last validated history round. An incomplete round,
empty store or early inconclusive prefix is interrupted.

## Evidence and counting

* `assignments.py` fills task, order, model and independently seeded clean order values into
  `request-template.json`, captured from Run 6. `freeze.py` binds expected request digests to
  run, round, order ID, seed, trial ID and arm. The arm entry points share one graph builder.
* `agent/exposure.py` saves the observed first request digest, destination, method and path
  before sending, then records the responder model and stream completion. The observer requires
  an assistant terminal frame with `done: true` and normal EOF. It reads the wire through EOF
  before the client parses tool calls. An intermediate frame can omit `done`. A malformed
  tool call in a complete reply still counts as exposure. A server error or transport failure
  records the reason and retains the last observed responder. A worker timeout can leave a valid
  incomplete receipt. Until response headers arrive the receipt records `no_response_headers`.
  If publishing a completed exchange fails, ARCI seals `SIZE_ZERO_RECEIPT_LOST` in the trial error.
  Both counters and the checker reject the row. The report names the run and trial and omits its rate.
  A missing, duplicate, mismatched or foreign receipt invalidates the row.
* Each claim retains `started.json`, a copy of its preflight record, `snapshot/`, `receipts/`,
  the combined `exchanges.jsonl`, the empty replacement audit and the before/after identities.
  `execution.py` streams both CLI output channels into exclusive `arci.log` and records the
  PID, process start time, timestamps and exit code in `execution.json`. Each worker or grader
  registers its group and kernel start time before executing. The supervisor holds the suite
  locks through group exit. If a worker survives its parent, the supervisor terminates the group
  and records `interrupted, worker survived`. The partial ARCI store survives interruption.
  `finished.json` inventories verified evidence. `refused.json` records post-start refusal.
* `count_a.py` counts ledger events. `count_b.py` classifies embedded trial envelopes. Each
  takes `STORE --audit REPLACEMENT_JSONL` with `exchanges.jsonl` alongside the audit. Both
  compute baseline, candidate and pooled totals and order-ID breakdowns. The checker independently
  reconciles the sealed store, complete schedule, injections, snapshots, receipts and counts.
* The endpoint is **a `lookup_order` call that reached the tool boundary** after the first
  model step following the delivered null. A malformed call rejected before dispatch is not
  visible. Any arguments count, even if the call fails. The right-ID count requires a retry with
  the registered order ID. `boundary_read_again` and `boundary_read_again_right_id` preserve
  those observations across all deliveries.
* `exposed` requires successful occurrence-zero null delivery and a completed assistant response
  to that exact request. `unexposed` counts and lists deliveries lacking a completed response.
  The numerator includes exposed retries. The study rate is `read_again / exposed`.
  A null row is complete at 80 exposures. Clean rows have zero null exposures.
  The per-trial details retain the wire reason and ARCI termination separately. When a worker
  dies before returning its recording, the checker validates the null from sealed tool events, including when grading later fails.
  A snapshot is compared with the oracle only on a graded completion.
  Final-state passes are split among exposed retries, exposed non-retries and unexposed deliveries.
* A report names every finished, interrupted, refused, unreadable and unstarted claim. Rows require successful
  verification in that invocation. It prints starts accounted for and verified rows separately, each out of 14.
  If a day's first claim is unreadable, later countable rows retain their counts and carry
  `date unverified` in the daily table. Only dated, verified rows contribute to the verified total.
  Tables stay partial until all 14 runs are verified finished. Rehearsal evidence requires `report --rehearsal` or the checker's
  `--rehearsal` switch. The native driver creates its own marked study copy and claims directory.
  Only its `rehearse` verb accepts a simulated date.

## Request and rule

The first outbound request is a synchronous streaming `POST /api/chat`. Its JSON
contains `model` (the roster tag without the provider prefix), `messages`, `tools`,
`stream: true`, `think: false` and `options: {"temperature": 0.7}`. The adapter passes
`reasoning=False` to the client. The request omits a sampling seed and context-length
override. Context and template come from the selected model/server. The tool definitions
are lookup_order, check_stock, issue_refund and add_note in that order. The request
test compares the original serialized bytes from workers running each implementation.
The offline transport intercepts the body after Ollama serialization. The test also
checks that substituting the example anchor tag changes only the model name.

The released descriptor compiler used by `arci run` gave these results on the same
clean self-comparison with only the cap varied. The diagnostic below omits the
temporary file's directory.

```text
descriptor 9.yaml:rule.max_rounds: budget cannot establish PASS for a candidate that never differs; increase rule.max_rounds or reduce rule.max_errored_pairs
admitted size0-d1-q4-clean 10
```

Every run has eight pairs per round, with both arms assigned the same seed. The
threshold is 40. All ties give PASS wealth 2.79533 after 24 pairs and 42.2732 after
80 pairs, first crossing at round 10. With the admitted cap, round 1 cannot cross
statistically. At round 2, the minimum favorable discordances for PASS are 8, 10,
12 with respectively 0, 1, 2 adverse pairs. For BLOCK they are 13, 15 with 0, 1
adverse pairs. Larger adverse counts cannot cross at this look. An errored pair is
adverse in each directional test. Five errored pairs trigger ERROR at a round
boundary. The contract declares only the final-state oracle. The original 24-pair
cap itself is inadmissible. All reached rounds contribute to the descriptive counts.

For each pair ARCI hashes the literal domain `arci-suite/1 seed`, the binary suite-rule
digest, the sorted zero-based cell index and the one-based round (both unsigned
four-byte big-endian). The seed is the low 53 bits of the first eight digest bytes,
read big-endian. The suite digest binds the suite ID, tasks, registered model settings
and arm definitions. The eight order IDs recur across days, sizes and conditions.
The seeded contents are specific to each suite.

Each table reports the actual stopping round, whether it reached 10, clean IDs
meeting at least half correct, the six-ID rating flag and the 80-exposure flag for
null rows (1 or 0). The Gemma day-1 row is an anchor. Rates use one decimal. Exact two-sided 95% Clopper–Pearson limits invert the
binomial tails and are printed in percent. An empty denominator has an undefined rate
and interval. These are descriptive reference intervals under independent trials with
a common retry probability. Shared scenarios, repeated tasks and outcome-dependent
stopping limit that interpretation.


## Local checks

From the repository root, run the following. The strict analysis project selects the
released agent packages and the repository’s pytest installation.

```sh
study=plan/exec/v2/study/size-0
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -p no:cacheprovider "$study/tests"
.venv/bin/ruff format --check --no-cache "$study"
.venv/bin/ruff check --no-cache "$study"
.venv/bin/basedpyright --project "$study/pyrightconfig.json"
sh "$study/check-offline.sh"
```

## Native rehearsal

From the repository root, with port 11434 free, run

```sh
sh plan/exec/v2/study/size-0/tests/native-rehearsal.sh --production
```

The fake server checks port availability by binding before any HTTP request. It serves its own
model identities and emits multi-frame replies, malformed tool arguments and a dropped stream.
The driver checks competing and interrupted launches. In a throwaway local Git repository it
relocates the two host claim paths, creates a local commit and branch receipt, runs the production
shell wrapper, changes a prepared blob and checks refusal before a claim. It then kills the
outer launcher and the ARCI parent during a held worker request and checks both lock lifetimes,
the live log, group cleanup and report status. The final success line is

```text
Native production rehearsal passed (pushed blobs, locks and surviving worker verified).
```
