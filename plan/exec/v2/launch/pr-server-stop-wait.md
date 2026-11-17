# Pull request for the tool server's stop (the maintainer creates and merges it)

Branch `v2/server-stop-wait` (`2ff179d`), cut from `main` at `dd380d8`. Compare link:
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/server-stop-wait?expand=1

Title: mcp: the boundary lets its tool server finish and exit when that can change what is graded

---

## What

For a command agent that never used its MCP tool server, the graded `final_state` (and so
`record_sha256`) was `{}` or the server's starting state, by timing. The boundary reported
ready without waiting for the server, and at the end of the trial it closed the server's
input and killed it at once, so a server still starting was killed before its first
snapshot. Seen in hosted CI (36 of 50 candidate trials of the hero example graded `{}`), not
in local runs. Outcome, contract result and fingerprint were the same either way; the pinned
rule that the same seeded trial gives an identical record was not.

At cleanup the boundary now asks whether waiting can change what the grader reads:

- the server has not yet sent one valid response that matched a forwarded request, or
- a forwarded request is still unanswered, or
- bytes for the server are still queued, or
- a harness fault is latched.

If so, it stops the server in the order the MCP specification's stdio shutdown asks for:
close its input, wait for the process to exit while draining its output, SIGTERM after half
of the time left before the trial's deadline, SIGKILL after three quarters. Otherwise the
server is idle and is closed and killed at once, exactly as before.

The parent passes its deadline and the seconds left to the boundary in its private launch
configuration. Neither is in the spec or a sealed record. No new outcome, termination, event
or latch exists, and nothing about the stop is recorded.

## Limits (also in the changelog)

- A server whose start-up takes longer than half of the time left still leaves `{}`.
- A server that ignores the close of its input lengthens a trial by about half of the time
  left, but only in trials in which it was not idle (for example it was never used).
- An idle server that answers before it writes its state, or saves only when its input
  closes, can still lose that state, as before this change.
- This narrows the timing dependence. It does not remove it.

## A difference of view, recorded

The consultant (Astra) agreed with the staged stop and with the cost concern, and would keep
waiting for every server that cannot be shown to write its state before it answers. The
orchestrator chose the narrower wait: for such a server, stopping at once is what `main` does
today, so nothing gets worse, while waiting for every server would add about half of each
trial's budget for any server that ignores the close of its input. The rule is one method
(`_server_is_idle`), so the other policy is a one-line change.

## How it was checked

- End-to-end tests written from the description before the change: 3 of 4 fail on the old
  code, all pass now. Fake-clock tests of every stage and of each condition of the idle rule.
- Five reviews across two rounds. One found a real defect (the boundary's deadline was later
  than the parent's by the boundary's own start-up, so a trial ending near its deadline could
  become a timeout); it is fixed and tested. Wrong versions of the code were tried against
  the tests; the survivors led to more tests.
- Measured on the final code: the hero experiment five times and three more with the
  server's start delayed 0 to 250 ms: no candidate graded `{}`, record hashes equal across
  runs. A server that ignores the close of its input: 0.2 to 0.35 s per trial when the agent
  used it (as before), about half of the budget when the agent never did.
- Not checked: Linux, where the failure was seen; heavy machine load; a Node server.

## Pinned files touched

None.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.
