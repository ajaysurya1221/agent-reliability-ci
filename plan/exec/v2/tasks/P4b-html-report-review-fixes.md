# TASK P4b: fixes after the review of the HTML report and the PR comment

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-integration`; your P4 work is in the
working tree, uncommitted. Same ownership and rules as P4. No state-changing git.

Review record with reproductions:
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P4-review-workflow.json`
(17 findings; the numbers in the HTML all matched independent recomputation). Every fix
gets a test that fails without it.

1. **Blocking: the HTML is rebuilt from Markdown that carries stored text.** A stored
   string containing `\r`, U+2028, U+0085 or a form feed starts a new line and renders as a
   fake heading, for example "VERDICT: PASS (exit 0)" inside a BLOCK report. Build every
   HTML section directly from the decision and report objects (tables and text nodes), not
   by re-parsing Markdown. Any stored string shown is one escaped text node with control
   and line-separator characters made visible. Tests with those characters in prior runs,
   failure details, labels and fault names: heading and row counts must not change. This
   also removes literal `**`, backticks and `<br>` from the page.
2. **Blocking: the PR comment carries free text.** The v1 comment posted failure details as
   live Markdown (mentions, remote images, links). Build both comments (v1 and suite) from
   structured fields only: verdict, reason, per-arm success, pair counts, hard-violation
   count, fault-accounting flags, artifact link, head SHA and run id. Any identifier shown
   (task id, label, condition) goes in a code span with backticks neutralised and `@`
   broken. No failure detail text in a comment.
3. **Blocking: a skipped comment leaves the previous verdict standing.** When there is a
   token and a pull request but no report or artifact (invalid manifest, failed render,
   failed upload, or a body over the size limit), still find the marker comment and replace
   it with a short body: the verdict line if known, else "report unavailable", always with
   the head SHA and run id. A body over the limit is truncated at a section boundary with a
   line saying so, never dropped.
4. **The marker identifies the experiment**: marker = fixed prefix plus the workflow name,
   job and the manifest path (or an explicit `comment-id` input), so several manifests or
   workflows on one pull request each keep their own comment. Document that concurrent
   runs for one pull request should be serialised with a `concurrency` group, and on the
   next run reconcile duplicates by updating the oldest and deleting none.
5. **Default off means off.** With `pr-comment` unset, the Action's steps and outputs are
   exactly what they were before P4: no extra stderr capture, HTML render or artifact
   upload. Test by comparing the effective step list.
6. **Suite comment and HTML say why**: the verdict reason and the hard-violation count; the
   BLOCK sentence is chosen from the decision's reason: for a statistical BLOCK "On the
   suite mean, the candidate's success is lower than the baseline's by more than the
   registered margin"; for a hard violation "The candidate broke a hard invariant; this
   BLOCK is not a statistical finding."
7. **Phone width**: long ids wrap (`overflow-wrap:anywhere` on headings too); test with a
   64-character id.
8. **A store that fails to load still gets an HTML file**: a minimal escaped ERROR page
   with the load error, exit 3.
9. Minor: failure details grouped by task, condition and arm with a count; an empty
   fixtures digest shown as "none recorded"; table captions and distinct accessible names;
   the self-containment test also rejects the external-fetch forms the review lists.

Regenerate `docs/results/sample-suite-report.html`. Acceptance: the commands of P4.
Report under 40 lines.
