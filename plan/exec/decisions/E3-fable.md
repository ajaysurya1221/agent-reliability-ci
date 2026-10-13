# E3 — README first screen: Fable's position (written blind, before reading E3-astra)

Written 2026-10-13 without opening `plan/exec/consults/E3-astra.md`.

## 1. First-screen text (everything before the first `## `)

```markdown
# agent-reliability-ci

**Did this change make your agent less reliable?**

ARCI runs your baseline and candidate repeatedly under the same predeclared tasks and injected
tool faults, returns `PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR` with an exit code, and can replay a
recorded failure offline.

Try it without cloning (seeded fixture, no model call, about a minute):

```bash
uvx --from agent-reliability-ci arci demo
```

Gate your own Python agent: install, scaffold one experiment from four references, run it:

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
```

`baseline + candidate → same frozen tasks and faults → repeated trials → verdict → minimise and replay`

**PASS means only this:** on this predeclared experiment, the candidate was not shown to be worse
than the baseline by more than the allowed drop. It is not a claim of absolute reliability.

A small first run will often be **INCONCLUSIVE**. That is a valid result, not a failure; run
`arci plan` before choosing a larger confirmatory experiment.

ARCI observes the calls that cross its tool boundary. It is not a sandbox, it does not replay
model inference, and a trace divergence shows where two runs differ, not why.

[Recorded result](#the-recorded-retry-regression) · [How it works](#how-it-works) · [What it does not do](#what-it-does-not-do) · [Evidence](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/reports/ci-gate-2026-10-06/REPORT.md)
```

Deviations from the memo draft: (a) "same predeclared tasks and injected tool faults" instead of
"same predeclared conditions" — the jargon table removes "conditions"; (b) "about a minute" is a
measured number (38 s on a 15-core laptop; CI runners slower) and is the honest version of
"≤2 min"; (c) the minimise/replay words stay plain English per the jargon table; (d) a one-line
link row replaces the badge block above the fold (badges move below).

## 2. What moves below the fold

New section order after the first screen:
1. `## The recorded retry regression` — the current lines 3–35 content: the headline numbers
   (192/200 vs 132/200, BLOCK, exit 1), evidence links, the hero `<picture>`, the re-derived
   sentence, then the badge row and the security-policy link.
2. `## Try the offline demo` — rewritten around `arci demo`: what the six steps do, the committed
   log excerpt (unchanged, it is the recorded run), and the honest sentence (item 4).
3. `## Verdicts and exit codes` (unchanged).
4. `## How it works` (unchanged).
5. `## Where it has been run` (unchanged).
6. `## The gate, measured against itself` (unchanged).
7. `## Gate your own agent` — descriptor first (`arci init`, `arci.yaml`, `arci schema`), the
   Python builder as the advanced path, the CLI list, GitHub Actions (pin → v0.8.0 in T12).
8. `## What it does not do` — kept, plus the two additions.
9. Independence paragraph (verbatim), `## Roadmap`, `## Development` (uvx/uv tool install first,
   clone route second).

## 3. Absolute URLs

Hero figure:
`<source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/main/docs/assets/hero-dark.svg">`
`<img src="https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/main/docs/assets/hero-light.svg" alt="...">`
(same for `where-*.svg`). Every first-screen link is absolute (`https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/...`); in-page anchors stay anchors.

## 4. The demo paragraph

"`arci demo` runs a packaged copy of the seeded inventory fixture (`arci.demo`): the same world,
agents, seeds and sample size as the recorded run, so it computes 192/200 and 132/200 fresh on your
machine. It is a reproduction, not the recorded evidence; the recorded run and its unedited log are
linked above."

## 5. "What it does not do" additions

- **`arci init` imports your code.** Reference validation imports the four modules (and calls the
  toolset factory once) in a child process, exactly as a trial would.
- **A fault that never fires is not a finding.** A fault names a tool; if the agent never calls that
  tool at that occurrence, the condition runs clean and nothing says so. Check the trace.
