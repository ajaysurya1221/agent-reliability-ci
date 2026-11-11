# Launch drafts for v2.0.0 (to be posted by the maintainer)

Written 2026-11-11 by the orchestrator. Every number here comes from a file in this
repository; the source is named beside it. Post nothing before v2.0.0 is on PyPI, and
replace `<REPORT_URL>` with the published HTML report's address.

Claims these drafts must not make (from `docs/STATISTICS_SUITE.md`): fewer runs than other
methods; a verdict from one run; per-task conclusions; anything about tasks outside the
suite; anything about the two models in general.

## 1. Show HN

**Title:** Show HN: ARCI – a pre-registered regression gate for LangChain agents (runs offline)

**Text:**

I built ARCI because "the agent eval passed" kept meaning "it passed this time". ARCI treats
an agent change like a clinical trial: you fix the tasks, the faults to inject, and the
decision rule before anything runs, and the rule is hashed into every trial so it cannot be
adjusted afterwards.

What v2 adds:

- A LangChain adapter. You give it your tools and your `create_agent` settings; it runs your
  agent behind a recorded tool boundary and injects tool timeouts, errors and empty results.
- A multi-task gate. Baseline and candidate run the same task-and-fault grid in rounds; the
  verdict is PASS, BLOCK, INCONCLUSIVE or ERROR, with a proved 2.5% bound on each wrong
  direction under stated assumptions. INCONCLUSIVE is a real answer, not a failure.
- A single-file HTML report, including how often each injected fault actually fired.

To check it does something, I pre-registered one comparison on my laptop and wrote down my
prediction first: could a 4B local model replace a 12B one on a 24-task order-desk suite
under four fault conditions? I predicted PASS. It was BLOCK after one round: 96 of 96
against 70 of 96. The report showed why: one task type, where the small model calls a tool
with a product code the order does not have. It also showed the injected fault fired in
24 of 24 trials for one model and 18 to 20 of 24 for the other, because the smaller model
sometimes skipped the lookup entirely. 18 minutes, no API key, no spend.
Report: <REPORT_URL>

Limits, plainly: the guarantee is for the suite you registered, not for other tasks; a PASS
is about the suite average and can hide one bad task (the per-task table sits beside the
verdict for that reason); nothing can PASS before about 80 paired runs at the default
margin; synchronous LangChain agents only for now.

    pip install 'agent-reliability-ci[langchain]'
    arci init --langchain && arci run arci.yaml

Repo: https://github.com/ajaysurya1221/agent-reliability-ci
I'm one person with AI pair programmers; the design records and every review are in the
repo. I'd like to hear where the assumptions break for your agents.

## 2. r/LangChain

**Title:** I wrapped `create_agent` in a fault-injecting regression gate and my own prediction lost

Short version of the Show HN text, leading with the adapter file (about 50 lines for the
example: tools, two settings functions, one `make_adapter` call) and the study table:

| | 12B model | 4B model |
|---|---|---|
| Trials passed | 96 of 96 | 70 of 96 |
| Injected fault actually fired (per faulted condition) | 24 of 24 | 18 to 20 of 24 |

Then: what is rejected today (async agents, interrupts, tools with injected arguments, tool
artifacts) and that those rejections are loud errors, not silent pass-through. Ask: which of
those matters most to you?

## 3. Short thread

1. "The eval passed" usually means "it passed this time". I built a gate that makes you
   write the rule down first. v2 works with LangChain agents and runs fully offline.
2. I pre-registered one test: can a 4B local model replace a 12B one on 24 tasks under tool
   faults? My written prediction: PASS.
3. Result: BLOCK in one round. 96/96 vs 70/96. 18 minutes on a laptop, no API key.
4. The useful part was the report: the small model skipped a lookup, so the injected fault
   never fired in a fifth of its trials. An eval that does not count that is comparing
   different things.
5. What it will not tell you: anything about tasks you did not register. Repo and report: …

## Sources for every number

- 96/96, 70/96, round 1, 18 minutes, fault firing counts: `plan/exec/v2/study/RESULT.md`
  and `report-run-1.md`.
- 2.5% bound and its assumptions: `docs/STATISTICS_SUITE.md`.
- "about 80 paired runs": the 79-pair floor, `bench/selfcheck_suite.py`.
- Adapter file size: `examples/langchain_quickstart/agent.py`.
