# R15: consult on the timing of the tool server's stop (read-only)

You are the consultant. You change no file and run no git command that changes state.
Answer in under 600 words. The code to read is in the worktree
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs` (commit `92f6ae0`: `main` plus the
atomic `state.json` write). Read there, not in the folder you were started in.

## The problem

For a command agent that never uses its MCP tool server, the graded `final_state` is `{}`
or the server's starting state, by timing. Seen in hosted CI on
`tests/acceptance/test_hero_decisions.py` (jev triage, variant `b`, 50 trials per arm,
`max_workers=8`): 36 candidate trials graded `{}`, 13 the starting state, 1 a 0-byte file
(that one is fixed by `92f6ae0`). Outcome, contract and fingerprint are the same either
way; only `final_state` and therefore `record_sha256` differ.

Why (file and line in the worktree):

- The boundary starts the server and prints `ready` at once; nothing waits for the server
  (`src/arci/mcp_boundary.py` 1904-1959). The parent starts the agent on `ready`
  (`src/arci/runner.py` 1188-1235).
- With decisions configured, the parent sends the boundary SIGTERM as soon as the agent has
  exited (`runner.py` 1254-1269). The boundary's `_cleanup` closes the server's stdin and,
  if `poll()` is None, kills it at once, with no wait in between
  (`mcp_boundary.py` 2056-2072). The grader runs after that.
- The Python bridge writes its first `state.json` at the end of start-up, then reads stdin,
  and exits on EOF (`src/arci/mcp_toolset_server.py` 140-160, 235-283). Start-up measured
  locally: 57 to 88 ms. The variant `b` agent is done about 90 ms after the boundary starts.
- Locally the split did not reproduce (0 of 650 candidate trials graded `{}`); with the
  server's start delayed by a scratch wrapper it did (27 `{}` and 23 starting state in one
  run), and for one trial id only `final_state` and `record_sha256` differed.

Pinned text it is measured against (`docs/AGENT_SEMANTICS.md`, frozen): lines 11-14 and
211-212 (same spec, identical envelope and `record_sha256` for a scripted client), 216-221
("No outcome may depend on scheduling luck"), 84-85 ("No fixed waits"), 172-173 (ready
frame), 191-192 (a server that cannot be started or exits early is `harness_error`),
201-203 (snapshot in the grader), 315-317 (with decisions the parent signals the boundary
as soon as the agent has exited). No pinned test covers an agent that makes no tool call
for equal hashes; `tests/acceptance/test_mcp.py` 118-123 pins FAIL/timeout for a hang.

The MCP specification (2025-11-25, lifecycle, stdio shutdown) says the client SHOULD close
the server's input stream, wait for the server to exit, send SIGTERM if it does not exit
within a reasonable time, then SIGKILL. The boundary skips the wait.

## The options

- (a) Readiness at the start: the boundary sends the server a probe (`ping`, or its own
  `initialize`) and prints `ready` only after any reply. The agent then cannot finish before
  the server's first snapshot.
- (b) Wait at the end: in `_cleanup`, after closing the server's stdin, wait a bounded time
  for the server to exit by itself before SIGKILL. A bridge still starting finishes its
  first snapshot, sees EOF and exits. A server that has to be killed is graded as today.
- (b') As (b), but a server that had to be killed makes the trial `harness_error`.
- (d) Make a missing `state.json` a grader error in the bridge's `snapshot`.
- (e) Leave it and say so in a document.

## My leaning

(b), with the bound derived from the trial deadline rather than a constant, and no change of
outcome for a server that ignores EOF. Reasons: it is the specification's shutdown order; it
is one small change in unpinned code; it also stops the kill from landing inside a write of
the pinned fixture server (`tests/acceptance/mcp_fixture_server.py`, which writes in place
and cannot be edited); (a) adds a message no agent asked for and may hang on a server that
ignores requests before `initialize`. My doubts: the boundary does not know the trial
deadline today (the parent does: `runner.py` 1278-1283 waits `deadline - now` for the
boundary); a server that ignores EOF would make every trial wait for the bound; and whether
"No fixed waits" allows a wait bounded by the deadline.

## What I need from you

1. Your choice among (a), (b), (b'), (d), (e) or a better one, in one line, and whether you
   disagree with my leaning.
2. For your choice: exactly where the wait or probe goes, what bounds it and where that
   bound comes from, and what happens to the trial's outcome and termination when the bound
   is reached (read `runner.py` 1238-1310 and the classification after it).
3. Every pinned sentence or pinned test your choice would contradict or break, quoted. If
   none, say how you checked.
4. The smallest test that fails today and passes after, with no dependence on timing luck.
5. What could go wrong that I have not listed.
