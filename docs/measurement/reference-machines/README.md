# Reference-machine demo timings

How long the packaged demo takes on a clean machine, measured by CI rather than by a person. It
backs the memo target for the packaged demo: p50 ≤ 2 min and p95 ≤ 3 min "on clean reference
machines" (`plan/research/forward-plan-2026-10-13.md`, adoption metrics).

## What a reference machine is

A fresh GitHub-hosted runner (`ubuntu-latest` and `macos-latest`) with:

- no ARCI checkout: the job never checks out this repository, and the demo runs in an empty
  `mktemp -d` directory;
- no uv cache: the five samples share one new, empty `UV_CACHE_DIR`, so sample 1 is cold
  (downloads and builds the tool environment) and samples 2–5 are warm (reuse it);
- Python 3.12 from `actions/setup-python` and uv from PyPI at the version CI pins;
- no secrets and no telemetry: the only network traffic is uv fetching the package from PyPI.

The command is the README's first-screen command pinned to the release under test,
`uvx --from agent-reliability-ci==0.8.0 arci demo`, run five times in a row.

## How the JSON is produced

[`.github/workflows/ttfv-reference.yml`](../../../.github/workflows/ttfv-reference.yml) runs on
pushes to `sprint/**` branches and on manual dispatch. For each OS it:

1. stamps `command_start` (UTC, whole seconds) and runs the command, piping its stdout and stderr
   through a filter that prefixes every line with its arrival time, into `sample-<n>.log`;
2. keeps the command's own exit code (not the filter's);
3. parses the logs into `reference-<os>.json`: per sample `command_start`, `demo_banner` (first
   line containing `arci demo:`), `demo_verdict` (first `VERDICT:`), `all_steps_held` (first
   `All six steps held`), `exit_code` and `uv_cache` (`cold` or `warm`), plus the runner (OS,
   architecture, image), the Python uvx ran arci with, `uv --version` and the package;
4. uploads the JSON and the logs as the artifact `ttfv-reference-<os>`, and fails the job if any
   sample exited non-zero or never printed `All six steps held`.

The maintainer downloads the artifact and commits the JSON here, whatever it shows. Failed
samples are kept. The JSON files are never edited after commit.

## Not receipts

These are machine timings. They are not TTFV receipts (`../receipts/`) and never count as cold
readers ([protocol](../ttfv-protocol.md) section 1.4): nobody reads the README, so the time to
open it, find the command and interpret the verdict is not in them. They bound the part of
time-to-first-verdict that the package and the network control; a person's time is longer.

## Reading p50 and p95

```
python plan/exec/scripts/reference_stats.py docs/measurement/reference-machines/reference-*.json
```

For each file it prints the five totals (`command_start` to `all_steps_held`, in seconds), then p50
and p95 by nearest rank, each against the target (120 s and 180 s). With five samples, nearest
rank makes p50 the third-fastest sample and p95 the slowest one, which is normally the cold
sample 1. A sample that failed has no total and ranks above every finished one, so a single
failure makes p95 "failed" and never within target.

Timestamps have one-second resolution, so each total is good to about ±1 s. Five samples on one
runner image are a spot check of that image on that day, not a distribution over users'
machines: GitHub-hosted runners vary in CPU and network, and a reader's laptop may be faster or
slower.
