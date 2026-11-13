# TASK R2: a clean model swap in the LangChain quickstart (for v2.1.0)

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2.1` (branch `v2.1/integration`, cut
from `main` at 2.0.0). No state-changing git. Frozen files (`FROZEN.sha256`, 65 entries)
untouched; if one looks wrong, stop and say so. Do not bump the version.

You own: `examples/langchain_quickstart/**`, the `LANGCHAIN_FILES` templates and
LangChain-init code in `src/arci/init.py` (kept byte-for-byte in sync with the example, as
today), new `docs/recipes/model-swap.md`, and tests under `tests/unit/examples/`,
`tests/unit/init/` and `tests/unit/docs/`. Do not touch `src/arci/report.py`,
`src/arci/suite_report.py`, `src/arci/html_report.py`, report goldens,
`docs/recipes/langchain.md`, `README.md` (another task owns them).

## The defect

`examples/langchain_quickstart/agent.py` builds `ToolRetryMiddleware(max_retries=0 if
candidate else 1, ...)`. With `ARCI_QUICKSTART_BASELINE` and `ARCI_QUICKSTART_CANDIDATE`
set to two **different** models, the comparison mixes two changes: the model and the
removed retry. The file's docstring says "identical inference settings". A user asking
"can I swap to this model?" gets a confounded verdict. The public study had to patch this
by hand.

The quickstart README (about line 91) documents the other real-model use: the **same**
model in both arms, which isolates the retry change. That use must keep working.

## Required behaviour

One rule, derived only from the two registered model ids (no new environment variable):

| Registered ids | Comparison | Baseline retry | Candidate retry |
|---|---|---|---|
| offline (`offline:scripted` both) | retry change (today's demo) | 1 | 0 |
| two real ids, equal | retry change | 1 | 0 |
| two real ids, different | **model swap** | 1 | 1 |

1. In model-swap mode the two arms' `create_agent` settings are equal in everything except
   `model`: same middleware classes and arguments, same system prompt, same temperature.
   One honest exception to state in the docs and docstring: `reasoning=False` is passed
   only for Ollama ids (`agent.py:23`); other providers keep their default, so two
   providers can differ there. A test builds both
   settings with two different fake ids (patch `init_chat_model`; no network, no real
   model) and asserts this, and asserts the retry-change modes still differ only in
   `max_retries`.
2. The offline run is unchanged: `arci init --langchain && arci run arci.yaml` in an empty
   directory still ends BLOCK with the same counts as 2.0.0. Existing tests that pin this
   must pass unmodified; if one needs editing, say why.
3. Nothing a reader sees may say "no-retry" for an arm that has the retry (the HTML report
   shows the YAML arm labels, `html_report.py:275`). Fix, per Codex's review: `register.py`
   writes the arm labels. In model-swap mode each label is that arm's model id (made safe
   for a label if the schema restricts characters; say what you did); in the retry-change
   modes it restores `retry` / `no-retry`. Labels enter the rule digest, the experiment id,
   seeds and trial `variant`, so this happens at registration, before a run, never after.
   `arci init` writes static templates and does not run `register.py`; the offline
   template and its registration identity stay byte-identical
   (`tests/unit/examples/test_quickstart_review.py:59`).
4. No new `mode` field. The mode is derived from the two registered ids, and
   `configuration.py:50` already compares the whole resolved settings with each task's
   registered settings, so a run whose environment implies another mode is refused. Add a
   test that shows this refusal.
5. `examples/langchain_quickstart/README.md`: a short section "Swap the model", the three
   commands, the table above in words, and one sentence that a different-model run no
   longer removes the retry (changed in 2.1.0). Keep the same-model section.
6. New `docs/recipes/model-swap.md`, under 80 lines, plain words:
   - the question it answers ("you changed the model; did the agent get worse on your
     tasks?");
   - the commands (`pip install 'agent-reliability-ci[langchain]'`, `arci init --langchain`,
     the two variables, `python register.py`, `arci run arci.yaml`, `arci report`);
   - how to read PASS, BLOCK and INCONCLUSIVE in one line each. Do NOT write "nothing can
     PASS before 80 pairs": that holds only when every pair is a tie (79 tied pairs at the
     defaults); pairs in the candidate's favour cross sooner (frozen test
     `tests/acceptance/test_suite_stats.py:871`). Say instead: verdicts are given only at
     the end of complete rounds, the quickstart's first look is at 96 pairs, and with every
     pair tied a PASS needs 79 pairs at the defaults;
   - a section "Do your tools raise or return their errors?": in the public study a tool
     that raised `ValueError` ended the trial unseen by the model. Two separate runs
     observed 70 of 96 trials passed without the error returned and 428 of 480 with it;
     they used different rounds and seeds, so this is two observations, not a measured
     effect (link `docs/results/order-desk-study.md`). Show this
     optional user middleware, to be added to **both** arms, and say it is not part of
     the template by default:

     ```python
     class ReturnToolErrors(AgentMiddleware):
         def wrap_tool_call(self, request, handler):
             try:
                 return handler(request)
             except ValueError as exc:
                 call = request.tool_call
                 return ToolMessage(content=f"Error: {exc}", tool_call_id=call["id"],
                                    name=call["name"], status="error")
     ```

     Before writing this section, confirm against the installed adapter
     (`src/arci/adapters/langchain.py`) that a user middleware of this shape is accepted
     and placed between ARCI's outer and inner middleware (`langchain.py:692`; Codex's
     review probed it on langchain 1.4.10). Add a small regression test under
     `tests/unit/examples/` using the existing in-process adapter helpers: the handler
     returns an error message to the next model turn and the failed boundary event is
     still recorded. No adapter change.
   - limits: one suite, your tasks only; a model swap verdict says nothing about other
     tasks.
   Links to `docs/recipes/langchain.md` and `docs/STATISTICS_SUITE.md`.
7. `LANGCHAIN_FILES` in `src/arci/init.py` stays byte-identical to the example files; the
   existing sync test must pass.

## Acceptance (worktree root)

```sh
.venv/bin/pytest tests/unit/examples tests/unit/init tests/unit/docs -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256
```

The LangChain tests need the adapter environment; the orchestrator re-runs them there
(`/Users/ajay/Developer/.arci-worktrees/v2.1-adapter-venv`). If it exists and is readable,
also run `…/v2.1-adapter-venv/bin/pytest tests/unit/examples tests/unit/init tests/unit/adapters -q`.

Known: about 65 tests fail inside the sandbox for socket and `ps` denials; name any other
failure. Report under 30 lines: files changed, last lines of each command, what you chose
for item 3, anything you could not do, risks.
