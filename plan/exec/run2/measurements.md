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
