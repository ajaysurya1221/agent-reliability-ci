**Choose (b), with staged shutdown and time reserved for boundary exit. I agree with your leaning as a mitigation; I disagree that it guarantees determinism.**

1. **Placement and bounds.** Pass the parent’s existing absolute monotonic deadline from [runner.py:976](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src/arci/runner.py:976) through the private boundary config at line 1158; keep it outside `TrialSpec` and sealed records.

   In [mcp_boundary.py:2064](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src/arci/mcp_boundary.py:2064), close server stdin, then await **process exit while draining stdout**, bounded by that deadline. Concretely, at cleanup entry take `t = monotonic()` and `R = max(0, deadline − t)`: allow EOF shutdown until `t + R/2`, send SIGTERM, then SIGKILL at `t + 3R/4` if necessary. Reserve the remaining quarter for reaping, the final frame, and boundary exit. Return immediately when the server exits. Do not restart the budget.

2. **Classification at the bounds.** Server escalation alone sets no new latch. If the boundary returns and exits before the parent deadline, existing classification applies: exit-zero agent → `completed`, then oracle grading; agent crash and infrastructure exits retain their mappings. Existing latches retain precedence.

   If the boundary remains alive at the **parent deadline**, [runner.py:1241](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/src/arci/runner.py:1241) kills both process groups; ordinarily this becomes `FAIL/timeout`, subject to latch and grader precedence. Waiting until that exact deadline therefore cannot preserve today’s classification. An abnormal boundary exit before it remains `ERROR/harness_error`.

3. **Pinned compatibility and remaining violation.** An event-driven wait bounded by the existing deadline is compatible with “No fixed waits.” Keep immediate parent SIGTERM with decisions configured; put the grace inside cleanup.

   I found no additional contradiction in the inspected MCP/decision semantics and acceptance tests. Preserve the hang assertion: `assert hung.outcome is Outcome.FAIL and hung.termination is Termination.TIMEOUT` ([test_mcp.py:123](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/tests/acceptance/test_mcp.py:123)).

   **The existing determinism gap remains:** “Determinism: for a scripted client the envelope must be identical across runs.” Also: “No outcome may depend on scheduling luck.” ([AGENT_SEMANTICS.md:211](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/AGENT_SEMANTICS.md:211), line 221.) Startup can exceed any finite grace; `{}` versus starting state can still differ. Neither (b′) nor (d) removes scheduling dependence merely by changing its classification.

4. **Smallest deterministic regression.** Use a fake clock and server whose initial snapshot becomes available only when cleanup yields to its exit wait after EOF. Killing first prevents publication. Assert the initial state is available and no kill occurred; separately advance the fake clock to test escalation. No sleeps or repeated trials.

   Executed the current `_cleanup` method in isolation against that fake using `.venv/bin/python -B -c …`. Output: `EOF -> KILL -> WAIT`, `State: {}`, followed by `AssertionError: cleanup killed server before allowing startup to complete`. This is a mechanism check, not acceptance evidence; the proposed implementation was not tested.

5. **Additional risks.** Undrained stdout can block shutdown; descendants can retain stdin; queued tool work can mutate state after agent exit; startup errors during cleanup can escape existing early-exit detection. Preserve final decision-worker fault polling. Grace also cannot protect an in-place write when escalation eventually kills it.

Files changed: **none**. Next: add the deterministic cleanup regression under `tests/unit/mcp/`.