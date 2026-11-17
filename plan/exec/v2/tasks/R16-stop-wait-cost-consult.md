# R16: consult on the cost of the staged stop for a server that ignores EOF (read-only)

You are the consultant. You change no file and run no git command that changes state.
Answer in under 450 words. The code is in the worktree
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (branch `v2/server-stop-wait`,
uncommitted change: `git diff`, plus two new test files under `tests/unit/mcp/`).
Your earlier answer is `plan/exec/v2/reviews/R15-boundary-timing-astra.md` in
`/Users/ajay/Developer/agent-reliability-ci`.

## Where we are

The staged stop you chose is built as you described: at cleanup entry t with R seconds left
before the trial's deadline, close the server's stdin, wait for the process to exit while
draining its stdout, SIGTERM at t + R/2, SIGKILL at t + 3R/4 (`stop_server` in
`src/arci/mcp_boundary.py`). Three reviews and a measurement:

- 900 hero trials (5 registered runs, 4 with the server's start delayed 0 to 250 ms): no
  candidate graded `{}`; record hashes equal across runs.
- A found and fixed defect: the boundary's deadline was later than the parent's by the
  boundary's own start-up, so a trial ending near its deadline could become FAIL/timeout.
  The parent now also passes its absolute monotonic deadline and the boundary takes the
  earlier of the two (`trial_deadline`).
- The cost, measured: for a server that does not exit on EOF, each trial lasts about R/2
  longer (0.25 s became 2.25 s at `max_seconds` 4; 3.3 s if it also ignores SIGTERM). R is
  nearly all of `max_seconds` when the agent finishes early, so at the default budget of
  30 s that is about 15 s per trial, and at 600 s about 300 s per trial.

## My concern

Servers that do not exit when stdin closes are plausible in practice (a Node server with an
open handle, a server behind a wrapper). For them this change turns a suite of a few minutes
into hours, silently. Before the change they were killed at once and graded correctly,
because an idle server that has answered every request has its state on disk already.

## The alternative I am considering

Wait only when waiting can change what the grader reads:

- the server has not yet sent a single message in this trial (it may still be starting, so
  its first snapshot may not exist), or
- a request the boundary forwarded has no reply yet (the server may be in the middle of a
  call or of a write).

In those two cases: the staged stop as built (R/2, 3R/4). Otherwise (the server has spoken
and nothing is pending): close stdin and, if it has not exited, kill it at once, as before
this change. No constant is introduced; the cost for a server that ignores EOF is then
limited to trials whose agent never used the server or left a call unanswered.

The other candidates: keep R/2 for every trial and document the cost; smaller fractions of
R (still scales with the budget); a constant cap such as min(R/2, 2 s) (I read
`docs/AGENT_SEMANTICS.md` 84-85, "No fixed waits", as speaking against a constant, and no
budget field for it exists in the frozen schema).

## What I need from you

1. Your choice among: keep as built; the "wait only when it can matter" rule; smaller
   fractions; a constant cap; something better. One line, and whether you disagree with me.
2. For the "wait only when it can matter" rule: is "the server has sent at least one
   message" a sound sign that its first snapshot exists, for the Python bridge and for the
   pinned fixture server (`tests/acceptance/mcp_fixture_server.py`)? Where does the boundary
   already hold "requests forwarded and not yet answered", and is that state reliable at
   cleanup on every exit path? Name the fields and lines.
3. What it would break or leave nondeterministic that the built version does not.
4. Whether skipping the wait for an idle server conflicts with any pinned sentence, quoted.
