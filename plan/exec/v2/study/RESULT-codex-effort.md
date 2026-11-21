# Result, the Codex effort comparison: INCONCLUSIVE at the cap; not an answer

This comparison is separate from the order-desk study. In D-30 the maintainer set D-29
aside for this comparison. The orchestrator and the consultant had advised against it.
The [registration] was committed at 15:46:34 UTC on 21 Nov 2026 (`8fc255a`) and pushed
at 15:46:36 UTC. No live trial preceded registration. There was one start. The first
trial began at 15:52:18 UTC and the driver ended at 19:03:47 UTC. The [raw files] are
in commit `632b201`. One commit intervened. [Decisions D-29 and D-30](../DECISIONS.md)

## Read this first

1. **INCONCLUSIVE after all 16 registered rounds.** The rule decided nothing. Whether
   project workers may stay at effort `high` is still an open question.
2. The registration required zero flagged trials to read a verdict as an answer. The
   audit flagged all 320. Even a PASS or BLOCK would not have counted.
3. A later, unregistered review found a fault in the audit rule. No trial's recorded
   commands returned an external copy of that trial's fix or another trial's answer.
   This changes neither the registered verdict nor the failed audit condition.

## What the tool printed

These lines are verbatim from a round-16 replay of `arci verdict` on the registered
rule and the two outcome CSVs. The table excerpt is the final round.

```text
VERDICT: INCONCLUSIVE (exit 2)

no test crossed

16 of 16 registered rounds supplied

| 16 | 160 | 12 | 139 | 9 | 0 | 2.42590e+01 | 1.44344e-02 | False | False | INCONCLUSIVE |

errored pairs through round 16: 0
```

Each ticket had equal weight. The boundary was a mean pass rate for high ten percentage
points below xhigh's. Neither the PASS test nor the BLOCK test reached its threshold of 40.

## In plain numbers

A pass required a completed turn, exit zero, and a nonempty allowed patch that applied
exactly and passed every registered visible and hidden check within the 90-second grading
allowance. Each arm had 1,200 seconds of agent time per trial.

| Effort | Pass | Fail | Error | Pairs started first |
|---|---:|---:|---:|---:|
| xhigh (baseline) | 147 | 13 | 0 | 80 |
| high (candidate) | 144 | 16 | 0 | 80 |

Of 160 pairs, only xhigh passed in 12, only high in 9, both in 135 and neither in 4.
Each arm started first on five tickets per round and eight times per ticket.

Each ticket had 16 trials per arm, zero errors and zero trials marked clean. The audit
columns give `outside_read` and `unauditable` trial counts, in that order.

| Ticket | xhigh pass/fail | high pass/fail | xhigh audit | high audit |
|---|---:|---:|---:|---:|
| csv-spaces | 16/0 | 16/0 | 14/2 | 9/7 |
| fault-report | 4/12 | 13/3 | 12/4 | 5/11 |
| init-write | 16/0 | 16/0 | 14/2 | 15/1 |
| interrupted-report | 16/0 | 16/0 | 16/0 | 16/0 |
| keep-output | 16/0 | 16/0 | 16/0 | 16/0 |
| kept-read | 15/1 | 3/13 | 15/1 | 16/0 |
| round-label | 16/0 | 16/0 | 8/8 | 4/12 |
| shorthand | 16/0 | 16/0 | 12/4 | 13/3 |
| snapshot | 16/0 | 16/0 | 16/0 | 16/0 |
| store-lines | 16/0 | 16/0 | 16/0 | 12/4 |

**fault-report favoured high.** All 15 failing submissions passed both visible tests.
With declarations `(9, 2)` and injection at 6, the row for start 2 remained unfired.

**kept-read favoured xhigh.** All 14 failing submissions passed all four visible tests.
The failing patches retried after an empty read. In the hidden check, the test installed
the replacement and then raised `FileNotFoundError` during open. All 14 returned
`unreadable`.

Sixteen trials per arm decide nothing about a ticket. Only these two had pairs where just
one arm passed. They favoured opposite arms, which helps explain why neither test crossed.

Elapsed seconds include setup and grading. The median, linearly interpolated 90th
percentile and maximum were unregistered. The last column counts trials under 120 seconds,
120 to under 300, 300 to under 1,200, and 1,200 or more, as registered. Neither arm hit
the agent time limit.

| Effort | Median (s) | 90th percentile (s) | Maximum (s) | Trial counts by band |
|---|---:|---:|---:|---:|
| xhigh | 116.735 | 237.948 | 319.281 | 85 / 74 / 1 / 0 |
| high | 88.565 | 147.005 | 185.502 | 115 / 45 / 0 / 0 |

## Registered conditions

The verifier received the driver’s totals and independently recounted the raw records
before seeing the write-up. Its findings are in `ce-verify.report.md`.

1. **HOLDS — registration before collection.** The local push record precedes the first
   trial. All 24 registered file digests matched. Before sealing, 131 stand-in tests
   passed with confinement on outside the sandbox. The published-tip check also passed.
2. **HOLDS — one record per start.** All 320 receipts matched the ticket, arm and order
   in the trial records. Start times matched the schedule. The recount checked every
   patch and transcript digest and matched each grade to its trial. All 160 pairs count.
3. **HOLDS — the decision replays.** All CSV rows matched their trials. Every round gave
   INCONCLUSIVE, exit 2. The final replay matched both saved decisions byte for byte.
   The run reached its cap with no partial round, service stop or time stop.
4. **FAILS — the audit required zero flagged trials.** All 160 pairs were affected.
   There were zero unattributed terminations, zero errored pairs and no three-error stop.

| Effort | Clean | Outside read | Unauditable | Denied events | Trials with a denial |
|---|---:|---:|---:|---:|---:|
| xhigh | 0 | 139 | 21 | 7 | 4 |
| high | 0 | 122 | 38 | 4 | 1 |

An outside-read flag took precedence over an unauditable event. Denials were counted
separately. All were attempts to run missing commands from the trial's own `.venv`.

## The audit, examined afterwards (not registered)

The recount grouped 16,956 flagged command frames by what the command targeted. Each cell
counts distinct trials / event frames. A command can have a start and a completion
frame. A trial can appear in several rows. “Outside” is a subset of “all”.

| Target (CSV code) | xhigh all | high all | xhigh outside | high outside |
|---|---:|---:|---:|---:|
| Own export, scratch, checks or text (A) | 160/8,372 | 160/6,305 | 119/416 | 102/364 |
| Python environment or runtime (B) | 155/683 | 157/546 | 42/83 | 39/66 |
| Shell, utilities or other runtime (C) | 160/533 | 160/464 | 19/23 | 16/17 |
| Shared dependency wheel cache (W) | 2/18 | 0/0 | 2/7 | 0/0 |
| Unsuccessful Git repository probe (G) | 7/13 | 10/18 | 3/3 | 7/7 |
| Local directory-name query for Git (Q) | 2/4 | 0/0 | 0/0 | 0/0 |
| All other categories | 0/0 | 0/0 | 0/0 | 0/0 |
| Unique total | 160/9,623 | 160/7,333 | 139/532 | 122/454 |

1. All 17,220 command frames lacked a working directory. The scanner could not resolve
   any relative path against the trial's own export.
2. Local names containing `mcp` and `server`, such as `mcp_toolset_server`, counted as
   remote tool use. This affected 204 xhigh and 211 high outside-read frames.
3. The scanner read a spaced `/` in Python code as a filesystem path.

Two xhigh trials, both on `shorthand`, searched a shared dependency cache in rounds 7
and 13. It held six wheels of this package containing the ticket's fix. The commands
selected dependency wheels. Their output returned no source for the fix. The recount
conservatively kept both trials out of its clean count.

The post hoc review set aside the two xhigh cache searches and found no evidence of an
external answer in the remaining 318 trials. The registered audit counted zero clean trials
in either arm. The 318 comprised 158 xhigh and 160 high trials. Command output cannot
establish every file a subprocess opened. No verdict was recomputed on a cleaned set, and
none will be.

The published [ledger](codex-effort/audit-posthoc.csv) combines event IDs and flags from
`trials.jsonl` with the verifier’s post hoc classifications.

- Expected SHA-256  `7e31ff358301ae0a524791060be3d2bdf6a5e21973a65735218fcae93f3a417a`
- CSV SHA-256 (match)  `7e31ff358301ae0a524791060be3d2bdf6a5e21973a65735218fcae93f3a417a`

## What went wrong in the design, stated now

No live trial was allowed before registration. The audit rule had never been tried on
a real event stream. The stand-in supplied a working directory that the real tool
omitted. In its last review the consultant had warned that the live tool might omit
evidence the audit needed. The registration listed that assumption as unverified.

The registered rule covered explicit paths outside the allowed roots. The trial environment
still permitted reads from a shared cache containing this package. At the chosen margin and
cap, INCONCLUSIVE was already the most likely end in two of the three planning cases.

## What this run does show

The driver and grader completed 320 trials with no error or deadline miss. Each sealed
decision records the hashes of both outcome CSVs through that round. From those CSVs,
`arci verdict` replays the same decision at every round. The consultant and orchestrator
both predicted INCONCLUSIVE, matching the result. Across ten past project fixes, the agent
passed in 291 of 320 trials. Both arms passed every trial on eight tickets. Across all ten,
xhigh passed 147/160 and high passed 144/160. The registered test could not rule out a
ten-percentage-point shortfall for high.

## What is not claimed

This run does not establish that high is as good as xhigh or that either is better.
It supports no claim about the vendor's model in general, other tasks or cost.
High had shorter recorded times. The comparison did not test a speed difference.
The later audit reading cannot make this run an answer.

## What follows for the project

Nothing changes. Project workers stay at `high` as before, without support from this run.
D-30 allowed one comparison. There will be no second run. D-29 stands.

## Errata

The live tool omitted the working directory assumed in the stand-in tests. The registered
audit treated unresolved reads as grounds to flag a trial, as specified. The raw commit
contains the grader's result for each submission. The full grader and preflight logs
are local. We found no change to the registered tickets, arms, order, rule or cap.

## If a comparison of this kind is run again

Advice for the record, not a plan for a new run. Before registration, validate the audit
offline against authentic CLI events from an unrelated task, including missing working
directories. Give each trial a dependency-only environment that cannot read project wheels,
and check the proposed cap’s chance of deciding at the chosen margin.

[registration]: PREREGISTRATION-codex-effort.md
[raw files]: codex-effort/runs-codex-effort/
