# HUMAN_INBOX — things only you can do (ordered by impact; drafts attached below)

Status as of the last orchestrator update: see the "Final state" line at the end of this file.

## 1. PyPI: register the pending trusted publisher (blocks publication)
Go to https://pypi.org/manage/account/publishing/ → "Add a new pending publisher" (GitHub):
- PyPI project name: `agent-reliability-ci`
- Owner: `ajaysurya1221`
- Repository name: `agent-reliability-ci`
- Workflow name: `release.yml`
- Environment name: `pypi`
Then re-run the failed `publish` job of the `Release` workflow for tag `v0.8.0` in the Actions tab
(or push the tag again after deleting nothing). If PyPI says the name is taken, tell the orchestrator
the alternative name: only the distribution name changes (the CLI stays `arci`).
If you prefer to publish by hand instead (token), from the tagged checkout:
```bash
uv build --no-sources && uv publish --token "$PYPI_TOKEN"
```
Never upload a version twice; PyPI versions are immutable.

## 2. Permissions still denied in `~/.claude/settings.json` (only if you want the orchestrator to do these itself next time)
`gh pr create`, `gh pr merge`, `gh release create`, `gh workflow run`, `uv tool install`, `curl`.
This run merged with plain git after lane CI, created no PRs, and left the GitHub Release to you
(item 3) if `gh release create` stayed denied.

## 3. GitHub Release v0.8.0 (if the orchestrator could not create it)
```bash
gh release create v0.8.0 --title "v0.8.0: install from PyPI, arci demo, arci.yaml, arci init" --notes-file plan/exec/release-notes.md dist/*.whl dist/*.tar.gz dist/SHA256SUMS
```
(the `dist/` files are the ones the Release workflow built; download the `dist` artifact of the
tag's run first, or run `uv build --no-sources` at the tag and compare SHA256SUMS).

## 4. Launch posts (your accounts; drafts below, each with one claim backed by a recorded run)
Order from the memo: GitHub release → Show HN → MCP community (after the Inspector recipe) →
Promptfoo/Inspect/Pydantic threads → local-model communities.

## 5. Outreach to the first pilot users (drafts below)

## 6. Follow-ups the orchestrator could not finish (see FINAL_REPORT.md "Next three steps")

---

# Drafts

## A. Release notes (plan/exec/release-notes.md is the file the orchestrator uses)
See `plan/exec/release-notes.md`.

## B. Show HN
**Title:** Show HN: ARCI – a CI gate for stochastic agent changes that can say "I don't know" and replay the failure

**Body:**
I built a small tool for a problem I kept hitting: an agent change (a prompt edit, a retry removed, a
model swap) looks fine on one run and breaks one time in five. ARCI freezes an experiment before any
trial runs (task, injected tool faults, sample size, decision rule), runs baseline and candidate
repeatedly, and returns PASS / BLOCK / INCONCLUSIVE / ERROR with an exit code. PASS means only
relative non-inferiority within a declared margin. INCONCLUSIVE is a first-class answer: small runs
usually get it, and the tool refuses to extend a run until it turns green.

What it is not: not a sandbox, not an evaluator, not a replacement for your evaluation framework.
It only sees calls that cross its tool boundary, and it replays the boundary, not the model.

Try it without cloning (seeded fixture, no model call):

    uvx --from agent-reliability-ci arci demo

That runs the recorded retry regression: 200 trials per arm, baseline 192/200, retry-removed
132/200, BLOCK, then the failing trace is diffed, minimised to one injected fault and replayed
offline. The recorded run and every archived decision re-derive byte for byte from the committed
records; the honest inconclusive runs are kept too.

Repo: https://github.com/ajaysurya1221/agent-reliability-ci — statistics contract, trust model and
limits are in the docs; I would rather hear what breaks than what looks nice.

## C. MCP community post (after the Inspector recipe ships; adjust to what shipped)
Inspector checks the MCP interface; ARCI compares an agent's behaviour under predeclared MCP tool
faults, repeatedly, with a frozen decision rule. The recipe `docs/recipes/mcp-inspector.md` shows
both in one CI job. Note (measured 2026-10-13): Inspector 2.10.1's bundled SDK (1.29.0) rejects
ARCI's bridge protocol revision 2026-07-28 with "Server's protocol version is not supported", so the
Inspector step is documented as blocked pending a newer SDK or a negotiation change on our side; the
recipe records that verbatim rather than working around it.

## D. Issue-thread comments (one claim each, no evaluator replacement)
- **Promptfoo #5947 (repeated-success measurement):** "If useful as a complementary workflow: ARCI
  runs baseline vs candidate repeatedly under injected tool faults with a preregistered
  non-inferiority rule and exits PASS/BLOCK/INCONCLUSIVE/ERROR; the recorded retry example is
  `uvx --from agent-reliability-ci arci demo`. It does not score outputs; it would sit next to
  promptfoo, not replace it."
- **Inspect AI (agent completion / scorer reliability threads):** "For the 'did the change make the
  agent less reliable' question specifically: ARCI compares two versions under the same predeclared
  faults with an exact binomial rule and keeps INCONCLUSIVE honest. Inspect's scoring and sandboxing
  stay as they are; ARCI would wrap a command agent behind its MCP boundary."
- **Pydantic AI #3138 (stronger agent testing):** "One narrow piece that may help: a preregistered
  repeated-trial gate for a Python agent function with injected tool faults; four references and
  `arci init` produce a runnable descriptor. It is not a test model and does not replace
  FunctionModel/TestModel."
- **agent-chaos:** "Your taxonomy is broader than ARCI's deliberately small fault set; interested in
  which one deterministic scenario would be worth an ARCI custom-fault recipe."
- **Chronicle:** "ARCI records boundary calls and requires exact consumption on replay; a
  conversion of one ARCI recorded trace into a Chronicle record (or a documented incompatibility)
  is on our next-90-days list; happy to compare envelopes."

## E. MCP Inspector docs PR text (title: "CI: protocol preflight with Inspector, stochastic resilience with ARCI")
One paragraph for the Inspector README/docs: "Inspector validates and exercises an MCP server
(connect, list, call). For regression-gating an agent that uses the server, ARCI
(agent-reliability-ci) runs the agent repeatedly behind a recording MCP boundary with predeclared
tool faults and returns an exact PASS/BLOCK/INCONCLUSIVE/ERROR verdict; the two are complementary.
Example job: <link to docs/recipes/mcp-inspector.md>." Send only after the protocol-version
incompatibility above is resolved on either side.

## F. Pilot outreach template (five target users from the memo)
Subject: 10 minutes to a first reliability verdict for <project> — would you try it and tell me where it breaks?
Body: I maintain ARCI, a CI gate for stochastic agent changes. I am looking for five people to run
the packaged demo (`uvx --from agent-reliability-ci arci demo`) and then one experiment on their own
agent, with a stopwatch, following docs/measurement/ttfv-protocol.md. I keep every receipt,
including the failed ones, in the repo. No telemetry; you fill in a JSON file by hand. The honest
expected first result is INCONCLUSIVE at the smoke size. If the whole thing takes more than
fifteen minutes or you get stuck, that is exactly the data I need.

---
Final state: <<filled in by the orchestrator at the end of the run>>
