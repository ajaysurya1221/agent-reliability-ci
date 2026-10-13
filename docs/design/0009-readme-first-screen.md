# 0009: the README first screen (v0.8.0)

Documentation decision by the orchestrator (Claude Fable 5.1) after two independent proposals, one by
the read-only consultant (gpt-6-astra, xhigh; `plan/exec/consults/E3-astra.md`) and one written blind
by the orchestrator (`plan/exec/decisions/E3-fable.md`), with the six differences settled by a third
consult (`plan/exec/consults/E3-tiebreak.md`) on 2026-10-13. Part of the v0.8.0 onboarding sprint
(task 11). The memo's draft (`plan/research/forward-plan-2026-10-13.md`, "The proposed first screen")
is the baseline.

## Problem

The README opens with the recorded retry result and a clone-based demo; the own-agent route is a
Python manifest builder six screens down. The memo's cold-read audit scores the 60-second reader
3.2/5 and finds no runnable own-agent path on the first screen.

## Decision

Everything before the first `## ` heading is the text below, at most 200 words counted by
`plan/exec/scripts/first_screen_words.py` (commands count; the assembled text is 190):

```markdown
# Did this change make your agent less reliable?

ARCI (agent-reliability-ci) runs your baseline and candidate repeatedly under the same predeclared
tasks and injected tool faults, grades each run with an independent success check, returns `PASS`,
`BLOCK`, `INCONCLUSIVE` or `ERROR` with an exit code, and can replay a recorded failure offline.

Try it without cloning (seeded fixture, no model call):

```bash
uvx --from agent-reliability-ci arci demo
```

Replace these example references with your project's importable Python functions:

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
```

`baseline + candidate → same predeclared tasks/faults → repeated trials → verdict → minimise/replay`

**PASS means only this:** for this predeclared experiment, the evidence supports that any reliability
drop from baseline to candidate is smaller than the allowed drop. It is **not** a claim of absolute
reliability.

A small first run will often be **INCONCLUSIVE**. That is a valid result; use `arci plan` before
choosing a larger confirmatory run.

ARCI observes calls that cross its tool boundary. It is not a sandbox, it does not replay model
inference, and trace divergence shows where runs differ, not why.
```

Below the fold, in this order: `## Try the offline demo` (what `arci demo` runs, then
`### Recorded result and evidence` with the 192/200 vs 132/200 BLOCK result, its links, the
re-derived sentence and the hero figure), `## Verdicts and exit codes`, `## How it works`,
`## Where it has been run`, `## The gate, measured against itself`, `## Gate your own agent`
(descriptor first; `### Advanced: Python manifest builder`; `### GitHub Actions`),
`## What it does not do`, the Independence paragraph verbatim, `## Roadmap`, `## Development`
(`### Availability and project status` with the badges, the security link and the availability line).

Rules kept: the two commands verbatim from the memo; the hero `<picture>` uses absolute
`raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/main/docs/assets/hero-{dark,light}.svg`
URLs and every relocated link from the old first screen is absolute, because PyPI strips `<source>`
and breaks relative links; the demo paragraph says `arci demo` runs a packaged copy of the seeded
fixture, computes 192/200 and 132/200 fresh and matches the recorded result, which is linked as
separate evidence; no runtime promise beyond measured facts; "What it does not do" is kept and gains
two items (reference validation imports user code; a fault naming a tool the agent never calls
silently never fires); the README table of verdicts and the gate table are unchanged.

## Positions and the rule that decided

Fable: `# agent-reliability-ci` title with the bold question; "not shown to be worse" (the memo's
wording); the recorded-result section first with the badges near the top; an intro line with a
measured "about a minute"; a link row closing the first screen. Astra: as adopted on all six (title,
PASS wording, section order, no runtime promise, no link row) with the merged "what" sentence. The
PASS wording changed because "not shown to be worse" also describes INCONCLUSIVE, while PASS is the
positive non-inferiority finding (`L > -delta`, docs/STATISTICS.md); the link row was cut because
it pushed the screen to 204 words. Rule: (d) the tie-break consult; (c) STATISTICS.md for the PASS
sentence; (b) the memo for everything it fixed.

## Not in v0.8.0

A Codespaces link, screenshots, animated output, a comparison table against other tools on the
first screen, any claim about adoption or external users.
