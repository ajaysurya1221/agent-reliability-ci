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

Only the cold samples are compared with the memo target. The target is about a first-time user,
and a warm run skips the downloads that dominate a first run, so pooling warm samples in would
pull the percentiles down and could report the target met when no first run met it. The warm
samples are reported separately, for information.

## Network traffic

The job touches the network only for:

1. `actions/setup-python` fetching the Python 3.12 build (from the runner's tool cache or
   GitHub's python-versions releases);
2. `pip install uv==<pinned>`: uv's wheel from PyPI;
3. each cold sample: uv resolving `agent-reliability-ci==0.8.0` against PyPI and downloading it
   and its dependencies (`pydantic`, `pyyaml` and their own dependencies) into that sample's
   empty cache; a warm sample may still query the PyPI index but finds the files cached; uv may
   also fetch a managed Python if it does not use the runner's interpreter;
4. one last `uvx … python` call (after the samples, timing nothing) that records the Python
   uvx ran arci with;
5. `actions/upload-artifact` uploading the JSON and the logs to GitHub.

The cold totals therefore include PyPI and the runner's network on that day.

## How the JSON is produced

[`.github/workflows/ttfv-reference.yml`](../../../.github/workflows/ttfv-reference.yml) runs on
pushes to `sprint/t18-**` branches and on manual dispatch (`workflow_dispatch`). For each OS it:

1. stamps `command_start` (UTC, whole seconds) and runs the command, prefixing every line of its
   stdout and stderr with its arrival time into `sample-<n>.log`;
2. bounds every sample: a sample still running after `SAMPLE_TIMEOUT_S` (600 s) is killed with
   its whole process group, its log is kept and ends with a `killed after` line, and it is
   recorded with `timed_out: true`, `exit_code: null` and `all_steps_held: null`. The sampling
   loop as a whole has `TIMING_BUDGET_S` (1200 s) inside the 25-minute job; a sample with no time
   left is not started and is recorded as timed out with `started: false`;
3. parses the logs into `reference-<os>.json` (this step runs even if the timing step failed):
   per sample `command_start`, `demo_banner` (first line containing `arci demo:`),
   `demo_verdict` (first `VERDICT:`), `all_steps_held` (first `All six steps held`),
   `exit_code`, `uv_cache` (`cold` or `warm`), `timed_out`, `started`, `timeout_seconds` and
   `uv_cache_entries_at_start`; plus the runner (OS, architecture, image), the Python uvx ran
   arci with, `uv --version`, the package and the design (`cold_samples`, `warm_samples`,
   timeouts);
4. uploads the JSON and the logs as the artifact `ttfv-reference-<os>`, and fails the job if
   there are not seven samples or any sample timed out, exited non-zero or never printed
   `All six steps held`.

The maintainer downloads the artifact and commits the JSON here, whatever it shows. Failed and
timed-out samples are kept. The JSON files are never edited after commit.

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
null or duplicate sample, `exit_code` null only for a timed-out sample). A file that fails is
reported as INVALID with its problems and no figures.

Otherwise it prints two blocks, never pooled. The **cold** block lists the totals
(`command_start` to `all_steps_held`, in seconds), then p50 and p95 by nearest rank and a
one-line verdict, each figure within or over its target (120 s and 180 s). With five samples,
nearest rank makes p50 the third-fastest sample and p95 the slowest. A sample that failed or
timed out has no total and ranks above every finished one; a percentile that lands on it is "not
reached", which is never within target. With fewer than five cold samples it lists the raw values
and makes no percentile claim ([protocol](../ttfv-protocol.md) section 8.3). The **warm** block
lists its totals the same way (two samples: raw values only) and is never compared with the
target. The script always exits 0: it reports, it does not gate.

Timestamps have one-second resolution, so each total is good to about ±1 s. Five cold samples on
one runner image are a spot check of that image on that day, not a distribution over users'
machines: GitHub-hosted runners vary in CPU and network, and a reader's laptop may be faster or
slower.
