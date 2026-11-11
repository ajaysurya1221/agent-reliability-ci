# TASK P2b2: fixes after the review of suite reports, triage, diff and plan

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-reports` (branch `v2/reports`, your
P2b work is committed). Same ownership and rules as P2b. No state-changing git.

The orchestrator's run outside the sandbox was green (2,900 passed). Three reviewers found
every suite report number correct against independent recomputation, and confirmed the
defects below. Record with reproductions:
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P2b-review-workflow.json`.
Every fix gets a test that fails without it.

1. **Blocking: fault accounting misreports custom faults.** A fault declared as a
   `module:function` factory whose perturbation `name` differs from the reference is shown
   as "declared, never fired" with 0 injections although it fired in every trial. Attribute
   injections to the declared fault by the name its perturbation actually records (resolve
   it the way the runner does), without importing user code in a way that can fail the
   report: if a factory cannot be resolved, say "cannot attribute" for that fault, never
   "never fired". Also: two declarations with the same name in one condition must each be
   accounted for (one that never fires is flagged). Injections whose `injected_by` matches
   no declared fault are listed as unattributed, never dropped.
2. **Blocking: v1 `arci plan` error output changed.** Missing arguments, a non-float rate
   and a stray positional must print exactly what v1.0.0 prints (compare with the main
   checkout `/Users/ajay/Developer/agent-reliability-ci`, which is v1.0.0). Add golden tests
   for those error paths. `arci plan <v1 manifest.json>` gives one clear line.
3. **Suite plan refuses projections it can compute.** The "too large" cut-off is wrong for
   most default grids: decide by a measured cost bound, and state the real limit. Homogeneous
   models are cheap; use that.
4. **Readable plan output.** Markdown shows each probability and expectation as a decimal
   truncated to six places beside or instead of the fraction; exact fractions stay in JSON.
   Stakes print as `1/4, 1/2`. The projection sentence appears only when a model was given.
5. **Suite triage keeps v1's stated limitations**, including the empty-fixtures one.
6. **Suite report shows the stored decision's status** (`match`, `absent`, `mismatch`) in
   Markdown and JSON; on a mismatch the report says so beside the verdict and exits 3, as
   `arci gate` does.
7. **Wording:** the `per_round` guarantee sentence names the mode and does not say "above"
   before the text it refers to; JSON carries the same sentences as Markdown; the prior-runs
   heading says it lists what the manifest records and that discovery covers the output
   root only.
8. The three private imports from `trace_check` in `triage.py`: keep them only if
   `trace_check` is not yours to edit; otherwise say in one comment line why the reuse is
   safe. No behaviour change.

Acceptance: the commands of P2b. Report under 40 lines: per item the change and its test;
command tails.
