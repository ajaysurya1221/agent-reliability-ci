# Run 6: the first start made no trial; a second start is registered

Written on 2026-11-22, after the first start of run 6 and before any trial of run 6.

## What happened

`PREREGISTRATION-run-6.md` was pushed in commit `0ca504d` at 06:01 UTC. A first guard
check refused to start because the local model server was not running; the server was
started and the check passed. The wrapper `run-6.sh real` was started at 06:02:57 UTC. It
passed every guard, claimed its one-start marker and reached its warm-up call, which is
outside the experiment. That call never returned. The orchestrator had started the wrapper
from a script whose standard input was an open channel, and the warm-up command waits for
the end of standard input before it sends its request. The model server's log shows no
request from it. After 54 minutes the orchestrator stopped the warm-up call; the wrapper
then stopped, as its rules say. The log of that start is `run-6.log`.

No trial of run 6 ran. No model request was made by the experiment. No store, no audit
file and no record of first exchanges exists. Neither arm ran or produced a trial outcome. The preflight logged both arms'
configurations.

## What is registered now

This amendment supersedes the original no-restart rule for one final start. The
experimental design and predictions remain unchanged. What is unchanged from
`PREREGISTRATION-run-6.md`:
the question, the scripted opening, the two arms and their texts, the tasks, the rule, the
cap, the conditions for reading the verdict, the predictions (both BLOCK) and what will
and will not be claimed. The descriptor and the agent code are byte for byte the same, so
the experiment id is the same.

Only the wrapper differs. `run-6b.sh` is `run-6.sh` with three changes: the warm-up call
and the tool's own process read their standard input from the null device; the marker and
the logs are named `run-6b-real.started`, `run-6b.log` and `run-6b-check.log`; and
`run-6b-digests.sha256` replaces only the wrapper entry. The wrapper checks this note
separately against published Git history.

The fault was in how the orchestrator launched the wrapper, not in the tool under study.
This second start is the last: if it fails before a verdict, that is published as the
result of run 6, and a new run would need a new registration.
