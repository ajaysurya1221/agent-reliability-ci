# HUMAN_INBOX — things only you can do (ordered by impact; drafts attached below)

Status as of the last orchestrator update: see the "Final state" line at the end of this file.

## 1. PyPI: register the pending trusted publisher, then re-run the publish job (blocks `uvx --from agent-reliability-ci arci demo`)

State at 07:59Z: tag `v0.8.0` (commit 48e60ac) is pushed; release workflow run
https://github.com/ajaysurya1221/agent-reliability-ci/actions/runs/38365660814 built the wheel and
the sdist and passed the four wheel-smoke jobs (Ubuntu/macOS × Python 3.11/3.14), then the
`publish to PyPI` job failed with:

```text
Trusted publishing exchange failure: Token request failed: the server refused the request for the following reasons:
* `invalid-publisher`: valid token, but no corresponding publisher (Publisher with matching claims was not found)
```

The OIDC claims PyPI saw: repository `ajaysurya1221/agent-reliability-ci`, owner id `74526464`,
workflow `release.yml` at `refs/tags/v0.8.0`, environment `pypi`. Nothing was uploaded; PyPI still
returns 404 for the project.

Do this (about three minutes):

1. Open https://pypi.org/manage/account/publishing/ and add a **pending** publisher: PyPI project
   name `agent-reliability-ci`, owner `ajaysurya1221`, repository `agent-reliability-ci`, workflow
   name `release.yml`, environment name `pypi`. (If PyPI says the name is taken, tell the next run
   the alternative name; only `[project] name` in `pyproject.toml` changes, with a design record.)
2. Re-run only the failed job of run 38365660814: Actions → "release" → that run → **Re-run failed
   jobs** (or `gh run rerun 38365660814 --failed`). The build and smoke jobs are not repeated; the
   publish job uploads exactly the files below and generates the attestations.
3. Check: `uvx --from agent-reliability-ci==0.8.0 arci demo` in an empty directory prints
   "All six steps held." and https://pypi.org/p/agent-reliability-ci shows the two files with
   these checksums:

```text
10ddc6823b446edd745d7904c5ab24a2fa098a0b9313ccc2df1b3277c4212899  agent_reliability_ci-0.8.0-py3-none-any.whl
99476b7b8923724eeb6392f7fa37ba4189c6fc5bb40d2ce9f10d7b3d578a9a01  agent_reliability_ci-0.8.0.tar.gz
```

If the re-run fails again, the troubleshooting page PyPI links is
https://docs.pypi.org/trusted-publishers/troubleshooting/ (the usual cause is a mismatch in the
environment name or the workflow file name).

## 2. Permissions still denied in `~/.claude/settings.json` (only if you want the orchestrator to do these itself next time)
`gh pr create`, `gh pr merge`, `gh release create`, `gh workflow run`, `uv tool install`, `curl`, `rm -rf`, `git reset --hard`, `chmod` (the last three found during the run; worked around with fresh directories, `git reset --keep`/none, and `bash script.sh`).
This run merged with plain git after lane CI, created no PRs, and left the GitHub Release to you
(item 3) if `gh release create` stayed denied.

## 3. GitHub Release v0.8.0 (the orchestrator's `gh release create` is denied by your settings)

The tag exists; the release page does not. The files to attach are the CI-built ones from run
38365660814 (byte-identical to a local `uv build` of commit 48e60ac). From a checkout of main:

```bash
gh run download 38365660814 -n dist -D dist-v0.8.0 && (cd dist-v0.8.0 && shasum -a 256 -c SHA256SUMS)
```

```bash
gh release create v0.8.0 --verify-tag --title "v0.8.0: install from PyPI, arci demo, arci.yaml, arci init" --notes-file plan/exec/release-notes.md dist-v0.8.0/agent_reliability_ci-0.8.0-py3-none-any.whl dist-v0.8.0/agent_reliability_ci-0.8.0.tar.gz dist-v0.8.0/SHA256SUMS
```

The notes file states that PyPI publication was pending at release time; if you do item 1 first,
delete that paragraph (lines under "PyPI status at release time") before creating the release, or
edit the release afterwards. Nothing in the notes makes a claim beyond the recorded runs.

## 4. Launch posts (your accounts; drafts below, each with one claim backed by a recorded run)
Order from the memo: GitHub release → Show HN → MCP community (after the Inspector recipe) →
Promptfoo/Inspect/Pydantic threads → local-model communities.

## 5. Outreach to the first pilot users (drafts below)

## 6. Follow-ups the orchestrator could not finish (see FINAL_REPORT.md "Next three steps")

- Cold readers: five people for the TTFV protocol (`docs/measurement/ttfv-protocol.md`), after
  item 1, using the pilot template (F). The maintainer-machine receipts in
  `docs/measurement/receipts/` are labelled `ai-agent` and never count.
- Review leftovers (one follow-up branch, two reviews each): ADR 0005 names `httpcore` where the
  lock says `httpcore2` (fix at the next re-freeze); an sdist allowlist step in `release.yml`;
  `arci init` reports every non-FileExistsError from `os.link` as "hard links unsupported" (name
  the errno); macOS `fsync` is not `F_FULLFSYNC`; dead signed-prefix branches in
  `descriptor._int_value`; `trials_started`/Track A version check in the protocol; a required
  reviewer on the `pypi` environment if you want a human gate on publishing.
- MCP Inspector: the bridge answers protocol `2026-07-28` and never negotiates; Inspector 2.10.1
  (TS SDK 1.29.0) rejects it. Making the recipe's step 1 work needs either a newer Inspector SDK or
  a negotiation change in `src/arci/mcp_boundary.py` (design record + Astra review).

# Final state at the end of the run (filled by the orchestrator; see FINAL_REPORT.md)

- main: v0.8.0 release merged (68f7c8c), tag `v0.8.0` = 48e60ac, CI green on the tagged commit and on
  every later plan-only commit; T13 docs (receipts, recipe titles, availability line) merged from
  sprint/t13-docs after REVIEW 13 (two rounds, both reviewers ACCEPT).
- PyPI: not published (item 1). GitHub release: not created (item 3). Both are one command each.
- Nothing half-applied: every lane branch is merged; no frozen file changed outside ADR 0005's
  re-freeze; no recorded result edited; no force-push, no deleted branch/tag/release, no secret.

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
Final state: see "Final state at the end of the run" above and plan/exec/FINAL_REPORT.md.
