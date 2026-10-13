# Run 2 measurements log (orchestrator-recorded)

## Reference-machine demo timing (T18), preliminary

- First live run of the workflow at cd44d22 (run 38449833039, old JSON schema: one cold + four warm
  samples per OS). macOS job cancelled when the next push superseded the run; ubuntu-latest
  (image ubuntu24 20261004.327.1, x64, Python 3.12.15, uv 0.12.5, package agent-reliability-ci==0.8.0)
  completed: sample 1 cold: resolve/install 1 s, total 169 s; warm samples 156, 146, 141, 137 s; all
  exit 0. Astra had earlier noted a macOS runner at 206 s in a CI wheel-smoke job.
- Reading: the package resolve is fast; the demo's 200-trial runs dominate, and the hosted runners
  are far slower than the maintainer's 15-core machine (73–80 s). Against the memo's target
  ("p50 ≤ 2 min, p95 ≤ 3 min on clean reference machines", line 287) the ubuntu cold sample is over
  the p50 target and the warm samples are 1:57–2:36. Proper figures (five cold samples per OS,
  separate warm block) come from the revised workflow (T18r1/r2) once a run completes without being
  superseded; those are reported in the final report whichever way they fall.
- macOS reference machine, same first run (from the uploaded logs; the parse step did not run):
  samples 1–4 held with totals 235 s (cold), 336, 417, 453 s; sample 5 was cut off at step 2 by the
  25-minute job limit. The warm samples are slower than the cold one and slow down monotonically,
  so the cache state is not what drives these timings; the cause (leftover processes, accumulating
  stores, runner throttling) is unknown and is a follow-up before any macOS number is called a
  reference timing. ubuntu samples got faster run to run (169 → 137 s).

## Reference-machine demo timing (T18r1 workflow, run 38451606669, 2026-10-13 ~19:05–19:22Z)

Five cold samples per OS (each with its own fresh `UV_CACHE_DIR`), `uvx --from agent-reliability-ci==0.8.0 arci demo`,
command_start → "All six steps held", 1 s resolution; package agent-reliability-ci==0.8.0, uv 0.12.5.

| Runner | cold totals (s) | cold p50 | cold p95 (= max of 5) | vs memo target (p50 ≤ 120 s, p95 ≤ 180 s) |
|---|---|---|---|---|
| ubuntu-latest (Linux x64) | 227, 226, 224, 222, 223 | 224 s | 227 s | over, over |
| macos-latest (macOS arm64) | 223, 213, 213, 227, 213 | 213 s | 227 s | over, over |

- The two warm samples per OS did not start: the 1200 s loop budget was spent by the five cold
  samples (5 × ~225 s), so they are recorded as timed out and the jobs' final check failed by
  design. T18r2 replaces the fixed budget with deadline arithmetic (40-min job) so all seven fit.
- The resolve/install share is ~1 s per cold sample on both runners; the demo's compute (two
  200-trial-per-arm experiments plus diff, minimise, replay, and the repaired agent's run) is the
  time. The first (superseded) run's ubuntu samples were faster (137–169 s), so hosted-runner
  variance between VMs is large; macOS no longer shows the monotonic slowdown seen in the first run
  (that run's warm samples shared one cache and ran back to back; cause still unknown).
- Honest reading against the memo (line 287): on GitHub-hosted runners the packaged demo misses the
  target by about 2×; it meets it only on the maintainer's 15-core machine (73–80 s). Either the
  target names a machine class or the demo on hosted runners must do less work (fewer trials per
  arm, or fewer of the six steps); that is a planning decision for the next run, not a workflow fix.
