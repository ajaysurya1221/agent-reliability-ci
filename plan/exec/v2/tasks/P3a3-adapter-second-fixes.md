# TASK P3a3: second fix round for the LangChain adapter

Lane B. Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-adapter` (branch `v2/adapter`,
P3a and P3a2 are committed). Same ownership and rules as P3a2. No state-changing git.

Three independent checkers re-ran the review's reproductions against your P3a2 fixes:
every item is fixed. They found the defects below, which the fixes introduced. Record with
evidence: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P3a2-verification-workflow.json`.
Each fix gets a test that fails without it.

1. **Set-up ends at graph entry, not at the first provider call** (major). Today a user
   middleware hook that raises on the first step (a guardrail in `before_model`, stock
   `PIIMiddleware(strategy="block")`, a `before_agent` check) is ERROR `agent setup failed`;
   on step 2 the same hook is FAIL. A candidate whose new guardrail over-blocks is a real
   regression and must be FAIL. Rule: set-up is the settings callable, `create_agent`,
   `task_to_input`, the graph rejecting its input, and what happens inside ARCI's inner
   handler before the provider is called (tool binding). Any exception raised by a user
   middleware hook at run time, on any step including `before_agent`, is agent behaviour.
   A run counts as started once the outer middleware's `before_agent` has run. Tests:
   `PIIMiddleware` block and a raising `before_model` guard give FAIL on step 1; a
   middleware that answers without calling the model followed by a later error gives FAIL.
2. **Drop the model type pre-check** (minor): a `with_config`-bound model and anything else
   `create_agent` accepts must work; invalid values still end as set-up ERROR.
3. **`ast.literal_eval` in replay rebuild** (minor): any exception from parsing only drops
   that candidate.
4. **Real error versus injected fault is decided by content, not by fault name** (minor):
   live re-raises the original whenever the tool body raised; replay reconstructs whenever
   the recorded failure is an `error` whose detail is not an injector's own text. State the
   remaining limit for custom perturbations in the module docstring.
5. **Accept `run_manager` on `_run`** (major): the canonical documented `BaseTool` subclass
   signature `_run(self, ..., run_manager: Optional[CallbackManagerForToolRun] = None)` must
   work as it did before P3a2, with native parity. Keep rejecting `config: RunnableConfig`.
6. **Pass `extras`, `metadata` and `tags` by reference** (minor), as native does.
7. **No reserved-name check on a single-input `Tool`'s function signature** (minor); keep
   the check on the raw argument keys.
8. **Deterministic test for the idle-clock reset** of the order gate (minor).
9. `functools.partial` tools stay accepted; say in the module docstring that native
   `create_agent` rejects them and ARCI does not.

Acceptance: the same five commands as P3a2. Report under 40 lines.
