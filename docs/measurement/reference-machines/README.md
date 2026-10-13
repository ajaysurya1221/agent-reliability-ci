# Reference-machine demo timings

How long the packaged demo takes on a clean machine, measured by CI rather than by a person. It
backs the memo target for the packaged demo: p50 ≤ 2 min and p95 ≤ 3 min "on clean reference
machines" (`plan/research/forward-plan-2026-10-13.md`, adoption metrics).

## What a reference machine is

A fresh GitHub-hosted runner (`ubuntu-latest` and `macos-latest`) with:

- no ARCI checkout: the job never checks out this repository, and the demo runs in an empty
  temporary directory;
- Python 3.12 from `actions/setup-python` and uv from PyPI at the version CI pins;
- no secrets and no telemetry.

The command is the README's first-screen command pinned to the release under test,
`uvx --from agent-reliability-ci==0.8.0 arci demo`.

## Cold and warm samples

Per OS the job takes seven samples, in this order:

- **five cold samples**, each with its own new `UV_CACHE_DIR` (a fresh temporary directory,
  checked empty before the sample starts; `uv_cache_entries_at_start` records the count, 0). uv
  has nothing cached, so each one resolves and downloads the package and its dependencies and
  builds the tool environment, as a first-time user's machine would;
- **two warm samples** that reuse the cache the fifth cold sample filled, so they measure a
  repeat run.

Only the cold samples are compared with the memo target, because the target is about a
first-time user. Cold and warm differ by uv resolving and downloading the package and its
dependencies, which measured 1–2 s on the hosted runners; nearly all of a sample's total is the
demo's own computation (two experiments of 200 trials per arm, the diff, the minimisation, the
replay, and the repaired agent's experiment). The warm samples are reported separately, for
information, and never pooled with the cold ones. As an example, not a guarantee: on 2026-10-13
(run 38451606669) the five cold samples took 222–227 s on `ubuntu-latest` and 213–227 s on
`macos-latest`, over both targets on both runners.

## Network traffic

The job touches the network only for:

1. `actions/setup-python` fetching the Python 3.12 build (from the runner's tool cache or
   GitHub's python-versions releases);
2. `pip install uv==<pinned>`: uv's wheel from PyPI;
3. each cold sample: uv resolving `agent-reliability-ci==0.8.0` against PyPI and downloading it
   and its dependencies (`pydantic`, `pyyaml` and their own dependencies) into that sample's
   empty cache; a warm sample may still query the PyPI index but finds the files cached; uv may
   also fetch a managed Python if it does not use the runner's interpreter;
4. one last `uvx … python` call (after the samples, timing nothing, skipped when the deadline
   leaves no room for it) that records the Python uvx ran arci with;
5. `actions/upload-artifact` uploading the JSON and the logs to GitHub.

The cold totals therefore include PyPI and the runner's network on that day.

## How the JSON is produced

[`.github/workflows/ttfv-reference.yml`](../../../.github/workflows/ttfv-reference.yml) runs on
pushes to `sprint/t18-**` branches and on manual dispatch (`workflow_dispatch`). For each OS it:

1. stamps `command_start` (UTC, whole seconds) and runs the command, prefixing every line of its
   stdout and stderr with its arrival time into `sample-<n>.log`;
2. bounds every sample by the smaller of `SAMPLE_TIMEOUT_S` (600 s) and the time left in the
   sampling loop (see [Deadline](#deadline)). A sample still running at its bound is killed with
   its whole process group, its log is kept and ends with a `killed after` line, and it is
   recorded with `timed_out: true`, `exit_code: null`, `all_steps_held: null` and a
   `timeout_reason`: `sample` when the 600 s per-sample limit killed it (a hang), `budget` when
   the loop's deadline cut it short (`timeout_seconds` < 600). A sample with under a second left
   is not started: `started: false`, `timed_out: true`, `timeout_reason: budget`;
3. parses the logs into `reference-<os>.json` (this step runs even if the timing step failed):
   per sample `command_start`, `demo_banner` (first line containing `arci demo:`),
   `demo_verdict` (first `VERDICT:`), `all_steps_held` (first `All six steps held`),
   `exit_code`, `uv_cache` (`cold` or `warm`), `timed_out`, `timeout_reason`, `started`,
   `missing`, `timeout_seconds` and `uv_cache_entries_at_start`; plus the runner (OS,
   architecture, image), the Python uvx ran arci with, `uv --version`, the package and the design
   (`cold_samples`, `warm_samples`, the timeouts, `job_start`, `reserve_seconds`,
   `budget_seconds_used`, `sampling_seconds`, whether the Python probe ran). It reads the
   per-sample journal line by line and never fails on it: every complete row is kept, a line cut
   off mid-write (a killed or cancelled step) becomes one
   `{"sample": null, "incomplete": true, "raw_prefix": <first 80 characters>}` entry with
   `journal_incomplete: true` at the top level, and every designed sample without a complete row
   is recorded as `missing: true` (not started, not timed out);
4. uploads the JSON and the logs as the artifact `ttfv-reference-<os>`, and fails the job if
   there are not seven samples, the journal is incomplete, or any sample is missing, was not
   started, was cut off by the budget, timed out, exited non-zero or never printed
   `All six steps held`.

The maintainer downloads the artifact and commits the JSON here, whatever it shows. Failed and
timed-out samples are kept. The JSON files are never edited after commit.

### Deadline

The job is killed at 40 minutes (`timeout-minutes: 40`, 2400 s), and the JSON must be written
before that. The first step records the job's start (`date +%s`); setup-python and the uv
install each have a 5-minute step timeout. When the timing step starts, the sampling loop gets

    budget = min(TIMING_BUDGET_S, 2400 − (now − job_start) − 300)

so a 300 s reserve is always left after sampling for the Python probe, the JSON, the upload and
the final check, however long setup took. `TIMING_BUDGET_S` is 2400 s, a ceiling that never
binds in a 40-minute job: the loop gets 2100 s less the setup time. The 120 s probe runs only if at
least 180 s remain before the job deadline, else it is recorded as skipped. The JSON's `design`
block records `job_start`, `reserve_seconds` and `budget_seconds_used`.

What this does and does not guarantee: seven samples at their full 600 s limit (4200 s) cannot fit
in 2100 s, so a slow enough run ends with samples cut off by the budget or not started, recorded
as such and failing the job. Seven samples of the measured ~225 s (1575 s), the probe and the
reserve fit when setup takes under 6 minutes (360 + 1575 + 120 + 300 = 2355 s ≤ 2400 s).

## Not receipts

These are machine timings. They are not TTFV receipts (`../receipts/`) and never count as cold
readers ([protocol](../ttfv-protocol.md) section 1.4): nobody reads the README, so the time to
open it, find the command and interpret the verdict is not in them. They bound the part of
time-to-first-verdict that the package and the network control; a person's time is longer.

## Reading p50 and p95

```
python plan/exec/scripts/reference_stats.py docs/measurement/reference-machines/reference-*.json
```

For each file it first checks the structure and the timestamps (stamps present and in order
`command_start` ≤ `demo_banner` ≤ `demo_verdict` ≤ `all_steps_held`, no negative duration, no
null or duplicate sample) and that no sample contradicts itself: `exit_code` null only for a
timed-out, not-started or missing sample; exit 0 only with all four stamps; no held stamp on a
timed-out sample; `uv_cache` `cold` or `warm`, and a cold cache empty at start; a
`timeout_reason` exactly when timed out, and consistent with `timeout_seconds`; a sample that was
not started is timed out by the budget unless it is missing from the journal; a missing sample
carries no stamps. A file that fails any check is reported as INVALID with its problems and no
figures.

Otherwise it prints two blocks, never pooled. The **cold** block lists the totals
(`command_start` to `all_steps_held`, in seconds), then p50 and p95 by nearest rank and a
one-line verdict, each figure within or over its target (120 s and 180 s). With five samples,
nearest rank makes p50 the third-fastest sample and p95 the slowest. A sample succeeds only if it
started, did not time out, exited 0 and carries all four stamps in order. Every other sample has
no total and is listed by what happened to it (`failed`, `timed out (hang)`, `cut off by budget`,
`not started`, `missing`); each ranks above every successful one, and a percentile that lands on
it is "not reached", which is never within target. With fewer than five cold samples it lists the raw values
and makes no percentile claim ([protocol](../ttfv-protocol.md) section 8.3). The **warm** block
lists its totals the same way (two samples: raw values only) and is never compared with the
target. The script always exits 0: it reports, it does not gate.

Timestamps have one-second resolution, so each total is good to about ±1 s. Five cold samples on
one runner image are a spot check of that image on that day, not a distribution over users'
machines: GitHub-hosted runners vary in CPU and network, and a reader's laptop may be faster or
slower.
