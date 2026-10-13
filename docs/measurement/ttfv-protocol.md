# Time-to-first-verdict and cold-read protocol

Protocol only; no receipt collected yet. [Template](receipt.template.json), [receipts](receipts/README.md).

## 1. Purpose and limits

1. It measures how long a person who has never used ARCI takes from opening the README to a valid
   first verdict they can interpret, and whether they can answer five questions about ARCI
   correctly from the README alone.
2. It feeds the targets in `plan/research/forward-plan-2026-10-13.md` ("Adoption plan"): packaged
   demo p50 ≤ 2 min and p95 ≤ 3 min; own fast agent p50 ≤ 10 min with at least 4 of 5 cold users
   ≤ 15 min; at least 80 % of cold readers answer all five questions correctly. The memo's "today"
   figures (demo about 8 min, own agent about 60 min) are unverified estimates, not measurements.
3. It does not measure: whether a verdict is statistically right (see `docs/STATISTICS.md`), how
   good or fast the reader's agent is, satisfaction, retention or adoption. Readers are
   self-selected, so receipts are not a representative sample.
4. Maintainer and AI-agent runs are labelled and never counted as cold readers. The maintainer
   timings in `plan/exec/measurements.md` (demo from the checkout, 38.2 s; from the wheel via
   `uvx` in an empty directory, 1:12 with environment creation) are not receipts.
5. No telemetry. A receipt is a JSON file a person fills in by hand and may contribute by PR.

## 2. Preconditions

1. A POSIX machine with Python 3.11+ and uv on `PATH`. No ARCI checkout anywhere the reader uses.
2. No prior ARCI install: `command -v arci` prints nothing and `uv tool list` does not list
   `agent-reliability-ci`. Record whether the uv cache already held the package (`uv_cache`: `cold`
   if run with a fresh `UV_CACHE_DIR`, else `warm`).
3. The package under test is published (PyPI) or a named wheel; record its version or wheel
   sha256. The README read is the one for that version, and its URL at a fixed commit is recorded.
   It must show both first-screen commands; if it does not, do not start.
4. The reader has not been coached: no walkthrough, prior demo or explanation of terms.
5. Track B only: a project directory, outside any ARCI checkout, in which a baseline, a candidate,
   a toolset factory and an oracle are importable (`module:function`), and each trial finishes in
   seconds. It is the reader's own agent (`project.kind: own`) or a copied sample tree
   (`sample`). Time spent writing these references before the attempt is not TTFV; if the reader
   writes them during the attempt, set `refs_preexisting: false` and keep the time in the total.
6. The facilitator stamps each milestone as ISO 8601 with a timezone (e.g. `date -u
   +%Y-%m-%dT%H:%M:%SZ` in a second terminal), to a few seconds; `notes` says how.

## 3. Track A, packaged demo

The reader follows the README to run `uvx --from agent-reliability-ci arci demo`.

| Milestone (`timestamps.*`) | When it is stamped |
|---|---|
| `readme_opened` | The README is on screen. **Clock starts.** |
| `command_start` | The reader presses Enter on the `uvx` command (install and run are one command). |
| `demo_banner` | The line `arci demo: the retry story, ...` appears (install and resolve done). |
| `demo_verdict` | The first `VERDICT: <X> (exit <n>)` line appears (step 2). |
| `all_steps_held` | `All six steps held.` appears and the command exits 0. **Clock stops.** |
| `interpretation_answered` | The reader answers the question in 5.3. |

Durations: `install` = `command_start` → `demo_banner`; `run` = `demo_banner` → `all_steps_held`;
`interpretation` = `all_steps_held` → `interpretation_answered`; `total` = `readme_opened` →
`all_steps_held`; `scaffold`, `agent_execution` and `outcome.store_validated` are null (the demo
checks its own stores). Track A's total excludes the interpretation span, which is recorded beside
it. A step that does not hold (exit 1) ends the attempt as a failure.

## 4. Track B, own fast agent

The reader follows the README to run, in their project directory, with their own experiment id
and references in place of the example ones:

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
```

If the chain runs as one line, stamp `install_done` and `scaffold_start` at the first output of
`arci init`, and `descriptor_written` and `run_start` at the first output of `arci run`.

| Milestone (`timestamps.*`) | When it is stamped |
|---|---|
| `readme_opened` | The README is on screen. **Clock starts.** |
| `install_start` | Enter on the install command (`uv tool install agent-reliability-ci`). |
| `install_done` | The install returns and `arci` is on `PATH`. |
| `scaffold_start` | Enter on the `arci init ...` that produces the descriptor used for the run. |
| `descriptor_written` | `arci init` exits 0 and `arci.yaml` exists. |
| `run_start` | Enter on `arci run arci.yaml`. |
| `verdict_printed` | The terminal shows `VERDICT: <X> (exit <n>)`. |
| `store_validated` | The facilitator's check in 4.3 completes. |
| `interpretation_answered` | The reader answers the question in 5.3. **Clock stops.** |

1. A first verdict is `PASS` (exit 0), `BLOCK` (exit 1) or `INCONCLUSIVE` (exit 2). A smoke-sized
   first run is expected to print INCONCLUSIVE; that is a valid first verdict and counts in full.
   `ERROR` (exit 3) means the experiment is invalid: stamp it in `failures` and let the reader
   continue; if no valid verdict follows, the attempt failed.
2. The clock stops only when all three hold: the verdict line is on screen; the run store exists
   with `manifest.json`, `trials.jsonl` and `decision.json` (at `runs/<experiment_id>/` unless
   the descriptor names another directory); and the reader has answered "what does this verdict
   mean?" correctly by the key in 5.3. A wrong answer is recorded and the attempt counts as a
   failure for TTFV.
3. Store check, run by the facilitator right after the verdict line, inside the clock:
   `ls runs/<id>`; `shasum -a 256 runs/<id>/decision.json`; `arci gate runs/<id>` must print the
   same verdict line and exit code; the sha256 must be unchanged. Any difference: set
   `store_validated: false` and the attempt counts as a failure.
4. Durations: `install` = `install_start` → `install_done`; `scaffold` = `scaffold_start` →
   `descriptor_written`; `run` = `run_start` → `verdict_printed`; `interpretation` =
   `store_validated` → `interpretation_answered`; `total` = `readme_opened` →
   `interpretation_answered`.
5. Agent execution is reported separately and only in Track B: `agent_execution` = the sum of the
   per-trial wall times ARCI records, `python3 -c "import json,sys; print(sum(json.loads(l)['usage']['wall_seconds'] for l in open(sys.argv[1]) if l.strip()))" runs/<id>/trials.jsonl`.
   Trials run in parallel (`project.workers`), so this sum can exceed the `run` span. It is never
   subtracted from `total`.
6. `outcome.init_attempts` counts `arci init` invocations. `descriptor_hand_edited` is true if the
   reader edited `arci.yaml` by hand before the run that produced the verdict. Re-running
   `arci init` with corrected flags is not hand editing.

## 5. Comprehension

1. Asked in writing once per reader, after the last milestone of the first track they complete;
   a second-track receipt sets `comprehension.answered_on` to the first receipt's file name and
   leaves the rest as in the template. The README may stay open. Answers are in the reader's own words.
2. Scoring: a scorer other than the reader marks each answer correct only if it contains every key
   element below (paraphrase is fine; a wrong extra claim, such as "PASS means the agent is
   reliable", makes it incorrect). `all_correct` is true only when all five are correct.

| # | Question | Key elements (all required) |
|---|---|---|
| q1 | What is ARCI? | (a) compares a baseline and a candidate version of an agent; (b) runs both repeatedly under the same conditions, including injected tool faults, fixed before the run; (c) returns a verdict (PASS, BLOCK, INCONCLUSIVE or ERROR) usable as a CI gate. |
| q2 | Who is it for? | (a) people changing an agent who want to know whether the change made it less reliable before merging; (b) ARCI must be able to call the agent so its tool calls cross ARCI's boundary: a Python function `agent(task, tools, rng)` or a command that speaks MCP over stdio. |
| q3 | What does PASS mean exactly? | (a) relative to the baseline; (b) not shown to be worse by more than the allowed drop (`delta`); (c) only on this predeclared experiment, and not a claim of absolute reliability. |
| q4 | What does it not do? Name two. | Two distinct items from: not a sandbox or security boundary; sees only calls across its tool boundary (not files, network, subprocesses the agent touches directly); does not replay model inference; a divergence shows where runs differ, not why; PASS is not absolute reliability; does not discover earlier runs or enforce an error budget across runs. |
| q5 | What are the first three commands for your own agent? | In order: install the `agent-reliability-ci` package (for example `uv tool install agent-reliability-ci`); `arci init <id>` with `--baseline`, `--candidate`, `--toolset`, `--oracle`; `arci run arci.yaml`. |

3. The interpretation question, "What does this verdict mean?", is asked once per attempt (Track
   A: about the `BLOCK` line for agent B). Correct iff, for the verdict shown: **PASS** meets q3's
   key; **BLOCK** says the candidate is worse than the baseline by more than the allowed drop (or
   broke a hard invariant) under these conditions; **INCONCLUSIVE** says there is not enough
   evidence either way, with no regression and no pass claimed (a larger run planned with
   `arci plan` would be needed); **ERROR** says the experiment is invalid and says nothing about
   the agents.

## 6. Facilitation without coaching

1. Before the clock starts the facilitator says only: "Please get ARCI's <demo | check on your
   agent> running from this page. Say when you are done or want to stop. I will only say
   'keep going'."
2. To any question the only allowed reply is "keep going". Reading the comprehension questions
   aloud and asking the interpretation question are not coaching.
3. Anything else (a hint, a pointed glance at the screen, fixing a typo) is a coaching event:
   append `{"at": <ISO time>, "what": <verbatim words or action>}` to `coaching_events`. A receipt
   with any coaching event is kept but not counted toward any cold-reader metric.
4. The attempt ends at the stop milestone or when the reader says they stop. There is no protocol
   time cap; a cap set in advance goes in `notes`.

## 7. Filling the receipt

1. Copy `receipt.template.json`, one file per reader per track; delete no keys. `track`: `demo` or
   `own-agent`; `reader.kind`: `cold`, `maintainer` or `ai-agent`. A milestone not reached or not
   in the track stays null. Durations are whole seconds as defined above; null if an end is null.
2. Every error, wrong turn or abandonment goes into `failures` as
   `{"at", "milestone", "what"}` with the first line of any error verbatim. Failed attempts are
   kept and contributed like successful ones.
3. Path: `docs/measurement/receipts/YYYY-MM-DD-<handle>-<track>.json`, the date of the attempt.
   No personal data beyond the handle.

## 8. Reporting

1. Use only receipts with `reader.kind: cold` and no coaching events. Report the count used and
   the count excluded, and why.
2. Per track, sort `total` ascending; a failed attempt counts as longer than every success.
   Percentiles are nearest rank: pN is the value at rank ceil(N/100 × n). If that rank is a
   failure, report "not reached". With fewer than 20 receipts p95 is the maximum; say so.
3. With fewer than five receipts in a track, make no percentile claim; list the raw values.
4. Report the "4/5 within 15 min" metric as k of n attempts with `total` ≤ 900 s, and the
   cold-read metric as k of n readers with `all_correct: true`.
5. Report `agent_execution` beside Track B totals (never subtracted), and Track A's
   interpretation correctness (k of n) beside Track A totals.

## 9. Kill criteria these receipts feed

From the memo's "Adoption plan":

1. `arci init`: if fewer than 7 of 10 cold users produce a runnable descriptor without syntax
   surgery by 2026-11-12, replace the interface rather than adding options. A Track B receipt
   counts as runnable without syntax surgery when `arci run` started trials on the `arci.yaml`
   that `arci init` wrote and `descriptor_hand_edited` is false.
2. Cookbook: if a recipe cannot get a fresh user to a valid verdict within its stated time
   budget, fix or remove it before adding more recipes. Receipts with `project.kind: sample`
   name the recipe in `project.description`.
