# Result, study Size-0: the size reading is withheld (the 2B build did not pass the clean check); the rows are published as they are

## Read this first

- The task was to look up an order and leave a note with the correct stock count.
- The prompt said “Retry an empty lookup once.”
- In the measured runs, the lookup came back empty. We counted how often each build looked again.
- The clean runs gave the model the order. They checked whether it could do the task without the fault.
- The 2B build passed 23 of 160 clean trials on day 1 and 16 of 160 on day 2.
- All three Qwen builds had to pass the clean check on both days for a size comparison.
- The 2B build did not, so no sentence about size is written. The tables give the counts for every build, including 2B.
- As counts, build by build: 4B looked again in 1 of 144 and 0 of 160 trials; 9B in 56 and 58 of 160; the unrated 2B in 33 and 32 of 160; Gemma 12B in 160 of 160.
- An agent that read no write-up counted every run again from the stored records. Its counts equal the report's.
- The size question covered three Qwen builds. Gemma ran separately as a reference. All used one prompt, one scripted mistake and one laptop. Nothing here speaks for hosted models or real agents.

## Question and setting

Run 6 recorded 0 repeat lookups in 24 trials with the 4B build and a plain empty reply. A reader asked whether other sizes of the same family would look again. [Run 6 result](RESULT-run-6.md)  
Size-0 repeated that setting with the 2B, 4B and 9B builds of Qwen 3.5. Gemma 12B ran separately as a reference.  
For each of eight order IDs, a script used the order ID as a stock code, got “Error: unknown SKU”, then called `lookup_order` with the correct ID.  
The model took over after that lookup. The clean run returned the order. The measured run returned the four characters `null`.  
A final-state pass required the exact stock note and an unchanged refund. A repeat lookup could count even if the task failed.

## What was registered and when

The registration was pushed on 27 November 2026 as `b381114`, before any Size-0 preflight probe or trial. One study test failed at that commit because it still expected a placeholder registration. The test was corrected and the input list frozen again in `3d4ee3d`, also before any probe or trial. All 14 run descriptions are byte-identical in the two commits. The runs used `3d4ee3d`. A link to the registration had been promised on the public discussion thread. It had not been posted there when trials began. The pushed registration commit is the public timestamp. [Registration](size-0/PREREGISTRATION-size-0.draft.md)

At registration the orchestrator had seen Board-0’s day-1 results under a different prompt. Board-0’s day 2 had yet to run. Run 6’s counts and the earlier Gemma thread report were already known. Neither the 2B nor the 9B build had seen a Size-0 task.

Both days used one Apple M5 Pro laptop with 24 GB of memory and Ollama 0.32.14. All four models used the nvfp4 number format, a 32768-token context and temperature 0.7. Thinking was off and no sampling seed was supplied. Each trial allowed 12 tool calls, 12 model steps and 120 seconds. [Model tags and digests](size-0/models.json)

Each slot ran clean, then null. Released ARCI 2.4.1 ran the same build and agent on both sides of each pair. Both sides shared an order and both counted. One round covered eight order IDs on each side, up to 10 rounds or 160 trials per run. The expected opening request for each of the 2,240 planned assignments was frozen before the probes. [Operator interface](size-0/INTERFACE.md)

## Results by day

**Delivered** means the scripted lookup returned the assigned null. **Exposed** means the model also completed a reply to the request carrying it. A delivery without a completed reply is **unexposed** and stays out of the rate. **Read again** counts an exposed trial if a later `lookup_order` call reached the tool after the model’s next step. Any arguments count, even if the call failed. A malformed call rejected before dispatch is invisible here. **Right ID** counts trials with a repeat lookup for the intended order.

An order ID qualifies if at least half its clean trials pass. A slot is **rated** that day if at least 6 of 8 IDs qualify. All columns from “Null trials” onward describe the measured run. Percent is read again divided by exposed. The exact 95% binomial intervals are references only. Paired trials share a seed, tasks repeat, and the stopping round can depend on outcomes. [Registered report](size0-evidence/report.txt)

### Day 1 · 27 November 2026

| Slot | Tag | Size | Clean passes/trials | Qualifying IDs of 8 | Rated | Null trials | Delivered | Exposed | Unexposed | Read again | Right ID | Percent | Exact 95% interval (%, reference only) | Final-state passes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| q2 | `qwen3.5:2b-nvfp4-ctx32k` | 2.2B | 23/160 | 0/8 | No | 160 | 160 | 160 | 0 | 33/160 | 33 | 20.6% | 14.6429–27.7276 | 7 |
| q4 | `qwen3.5:4b-mlx-ctx32k` | 4.5B | 86/96 | 8/8 | Yes | 144 | 144 | 144 | 0 | 1/144 | 1 | 0.7% | 0.0176–3.8083 | 1 |
| q9 | `qwen3.5:9b-nvfp4-ctx32k` | 9.4B | 112/160 | 8/8 | Yes | 160 | 160 | 160 | 0 | 56/160 | 56 | 35.0% | 27.6388–42.9283 | 49 |
| g12 | `gemma4:12b-mlx-ctx32k` | 12.4B | 160/160 | 8/8 | Yes | 160 | 160 | 160 | 0 | 160/160 | 160 | 100.0% | 97.7208–100.0000 | 160 |

### Day 2 · 28 November 2026

| Slot | Tag | Size | Clean passes/trials | Qualifying IDs of 8 | Rated | Null trials | Delivered | Exposed | Unexposed | Read again | Right ID | Percent | Exact 95% interval (%, reference only) | Final-state passes |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| q9 | `qwen3.5:9b-nvfp4-ctx32k` | 9.4B | 112/160 | 8/8 | Yes | 160 | 160 | 160 | 0 | 58/160 | 58 | 36.2% | 28.8078–44.2118 | 54 |
| q4 | `qwen3.5:4b-mlx-ctx32k` | 4.5B | 141/160 | 8/8 | Yes | 160 | 160 | 160 | 0 | 0/160 | 0 | 0.0% | 0.0000–2.2792 | 0 |
| q2 | `qwen3.5:2b-nvfp4-ctx32k` | 2.2B | 16/160 | 0/8 | No | 160 | 160 | 160 | 0 | 32/160 | 31 | 20.0% | 14.1004–27.0447 | 3 |

Every null-run final-state pass in the tables came from an exposed trial that read again. Each row had zero passes without a repeat lookup and zero unexposed passes. There were no unexposed trial IDs to list. The report marks every run date verified. Both counts found 58/160, exactly 36.25%. The registered report displays 36.2% and the blind recount rounds the half up to 36.3%.

## Read again by order ID

Each cell counts trials that read again out of exposed trials for that order. On day 1 the single 4B retry was for ORD-124. On day 2 the 2B build read again in 6 trials for ORD-118. In 5 of those it used the right ID.

| Order ID | Day 1 · 2B | Day 1 · 4B | Day 1 · 9B | Day 1 · Gemma 12B | Day 2 · 9B | Day 2 · 4B | Day 2 · 2B |
|---|---:|---:|---:|---:|---:|---:|---:|
| ORD-103 | 5/20 | 0/18 | 10/20 | 20/20 | 8/20 | 0/20 | 4/20 |
| ORD-106 | 2/20 | 0/18 | 9/20 | 20/20 | 8/20 | 0/20 | 2/20 |
| ORD-109 | 4/20 | 0/18 | 4/20 | 20/20 | 6/20 | 0/20 | 2/20 |
| ORD-112 | 0/20 | 0/18 | 7/20 | 20/20 | 4/20 | 0/20 | 3/20 |
| ORD-115 | 5/20 | 0/18 | 8/20 | 20/20 | 6/20 | 0/20 | 5/20 |
| ORD-118 | 8/20 | 0/18 | 8/20 | 20/20 | 11/20 | 0/20 | 6/20 |
| ORD-121 | 2/20 | 0/18 | 5/20 | 20/20 | 6/20 | 0/20 | 5/20 |
| ORD-124 | 7/20 | 1/18 | 5/20 | 20/20 | 9/20 | 0/20 | 5/20 |

## Reading under the registered rule

**The orchestrator withholds the size reading.** All three Qwen builds had to be rated and complete on both days. Every null run was complete, with at least 80 exposed trials. The 2B build was unrated on both days. With the order supplied, it passed 23/160 and 16/160, and 0/8 IDs qualified on either day. The registered rule ends there. The rows are published as they are.

The 4B build read again in 1/144 trials on day 1 and 0/160 on day 2. Run 6 recorded 0/24. The 9B counts were 56/160 and 58/160, about 35% each day. The unrated 2B counts were 33/160 and 32/160, about 20% each day.

Gemma 12B read again in **160/160** trials with stored records. The public thread on 22 November reported **24/24** and said it reused Run 6’s seeds. This repository has no trial records for that count, and the released runner generates separate seeds for each suite. Gemma sits outside the three-build rule.

## Predictions against outcomes

| Registered prediction | Observed outcome |
|---|---|
| Consultant, 2B about 5% (plausible range 0–50%) | 20.6% and 20.0%. Both were above the estimate and inside the range. Both rows were unrated. |
| Consultant, 4B about 3% (0–15%) | 0.7% and 0.0%. Both were below the estimate and inside the range. |
| Consultant, 9B about 35% (0–90%) | 35.0% and 36.2%. Both were inside the range. |
| Orchestrator, 4B at most 5% | 0.7% and 0.0%. Both met the bound. |
| Orchestrator, about a 40% chance of 2B being unrated on at least one day. If rated, at most 10% read again. | 2B was unrated on both days. Neither day tested the conditional 10% prediction. |
| Orchestrator, 9B about 50%, with high uncertainty | 35.0% and 36.2%, both below the estimate. |
| Orchestrator, about 30% chance of “ordered by size”, 30% of “close”, 40% of a withheld reading or another pattern | The reading was withheld, within the 40% category. Neither numerical classification was applied. |
| Orchestrator, Gemma 12B at least 90% | 160/160 (100.0%) on its scheduled day. |

“Ordered by size” required the 2B and 9B rates to differ by at least 25 percentage points in the same direction on both days, with 4B between them, ties allowed. “Close” required the highest and lowest rates to be within 10 points on each day. Both rules required rated, complete rows. The consultant also cautioned against attributing a repeated difference to parameter count. The maintainer supplied no prediction.

## Every scheduled run

All 14 scheduled runs started once and finished. The registered report says “starts accounted for: 14/14” and “verified rows: 14/14”. Day 1 ran from 17:09 to 18:08 IST on 27 November 2026 (eight runs). Day 2 ran from 00:19 to 01:04 IST on 28 November (six runs). The stored verdict checks a comparison of each model with itself. It carries no study result. [Day 1 log](size0-evidence/day1.log) · [Day 2 log](size0-evidence/day2.log)

| Run | Start (IST) | End (IST) | Trials | Stopping round | Stored check verdict |
|---|---|---|---:|---:|---|
| `size0-d1-q2-clean` | 17:09:30 | 17:15:29 | 160 | 10 | INCONCLUSIVE |
| `size0-d1-q2-null` | 17:15:34 | 17:20:32 | 160 | 10 | INCONCLUSIVE |
| `size0-d1-q4-clean` | 17:20:42 | 17:25:25 | 96 | 6 | PASS |
| `size0-d1-q4-null` | 17:25:34 | 17:30:01 | 144 | 9 | PASS |
| `size0-d1-q9-clean` | 17:30:14 | 17:40:02 | 160 | 10 | INCONCLUSIVE |
| `size0-d1-q9-null` | 17:40:15 | 17:49:12 | 160 | 10 | INCONCLUSIVE |
| `size0-d1-g12-clean` | 17:49:22 | 17:58:29 | 160 | 10 | PASS |
| `size0-d1-g12-null` | 17:58:38 | 18:08:43 | 160 | 10 | PASS |
| `size0-d2-q9-clean` | 00:19:50 | 00:29:55 | 160 | 10 | PASS |
| `size0-d2-q9-null` | 00:30:08 | 00:39:30 | 160 | 10 | INCONCLUSIVE |
| `size0-d2-q4-clean` | 00:39:39 | 00:47:49 | 160 | 10 | PASS |
| `size0-d2-q4-null` | 00:47:58 | 00:52:54 | 160 | 10 | PASS |
| `size0-d2-q2-clean` | 00:53:02 | 00:59:02 | 160 | 10 | INCONCLUSIVE |
| `size0-d2-q2-null` | 00:59:07 | 01:04:00 | 160 | 10 | INCONCLUSIVE |

On day 1 both 4B runs stopped before round 10. The clean run finished at round 6 with 96 trials. The null run finished at round 9 with 144 trials. Both reached their recorded stopping point. Every reached round counted.

## What happened around the runs

The original plan put Size-0 after Board-0. The maintainer moved Size-0 day 1 into the gap between Board-0’s two days on the same laptop. On 27 November at about 14:13 IST, Ollama was stopped so that the launcher could be rehearsed against a fake server; no study model answered in that rehearsal. Ollama was then started again with the same version and the same three recorded settings. The 2B and 9B model tags were downloaded between the two Board-0 days. The studies shared a lock to keep their runs apart. [Board-0 result](RESULT-board-0.md)

Before any trial, the orchestrator used the preflight probe times to estimate about 2 hours 20 minutes for all eight runs, with the last start near 19:15, ahead of the 21:00 cutoff. The decision at 17:09:24 IST was to start that day without the thread post. At 23:15 the stop check found no Size-0 run alive and interrupted nothing. Board-0’s last run ended at 00:18 on 28 November. Size-0 day 2 started afterward, with the lock free and the Qwen slots in reverse order. [Go decision](size0-evidence/go-decision.txt) · [Stop log](size0-evidence/stop.log) · [Day 2 log](size0-evidence/day2.log)

## Checks

**Independent recount.** An agent that was given only the stored records (sealed stores, receipts, exchange lists, the task list and the registered text of what is counted) and read no write-up and no count file counted all 14 runs again with code of its own. Its trials, final-state passes, delivered, exposed, read-again and right-ID counts, its clean ratings and its stopping rounds equal the report's for every run. Every trial matched exactly one receipt, with none missing or extra. It decided "exposed" in two ways (the receipt's completion flag, and the events that followed in the trial record); the two agree on all 1,104 null trials. Three things it noted: two 2B trials ran out of their tool-call budget after answering the null; on day 2 one 2B trial looked again with `ORD` in place of `ORD-118`, which counts as a read again and not as a right ID; and the receipts hold request digests and response metadata, not text, so it could not read the requests themselves. For each of the 2,160 trials that ran, the study's checker matched the recorded digest of the opening request to the digest registered for that trial.

**The study's checker.** `check_evidence.py` was run on a copy of the evidence unpacked from [`size0-evidence/claims.zip`](size0-evidence/claims.zip) ([how to check it](size0-evidence/README.md)) (2,529 files; SHA-256 `fcb0bb543a83392927558f850e6e70f976dcced81d80347a847841a66a7516be`) and printed "14 finished runs verified". The process registry and the lock file are left out of the zip; the checker does not read them.

## What this cannot show

- The three Qwen models are separately released builds. Their training, distillation and templates can differ along with size. The study cannot establish a cause for the counts.
- The 2B retry rate describes a build that mostly failed the task even when the lookup returned the order.
- The size question covers one family, one prompt, one scripted mistake and one stock-note instruction with eight order IDs, on one laptop and one server version. The results do not extend to hosted models or real agents.
- The script chose the opening calls. The study gives no estimate of how often a model makes that mistake on its own.
- The comparison between slots was uncontrolled. The IDs recurred, but each suite had its own seeded order contents and the slots ran one after another.
- Run 6 also tried a reminder in place of the empty reply. Size-0 did not repeat that arm, so whether a reminder helps the 2B or 9B build remains open.

## Departures from the consultant’s advice

The consultant proposed 48 fixed assignments per size and day, with sizes interleaved in blocks on shared seeded orders. The released runner requires a cap of at least 10 rounds for this setup and gives each suite its own seeds. Size-0 used that runner, with up to 160 trials per run. It ran whole suites in sequence and reversed the Qwen order on day 2.

The proposed admission test required success on 16 of 20 toy-tool probes. Size-0 recorded five toy-tool probes per preflight, checked identity and context, and used performance on the clean task for the rating. All 18 preflights qualified. All 90 probes produced a tool call the software could read. One 2B reply did not repeat the tool's token. The individual records and timings are under `claims/preflights/` in `claims.zip`. The proposed Gemma reference had 24 trials. Gemma instead received a full clean run and a full null run on day 1. The registration retained the consultant’s 25- and 10-percentage-point thresholds. [Registered departures](size-0/PREREGISTRATION-size-0.draft.md) · [Design differences](size-0/DEVIATIONS.md)

## Related work

Earlier work studies how the delivery of an error changes recovery and how models respond to loud and quiet faults. [arXiv 2611.11581](https://arxiv.org/abs/2611.11581) · [arXiv 2610.10062](https://arxiv.org/abs/2610.10062)

AgentRobustBench reports 21 models from 1.5B to 32B under 22 kinds of perturbation. AgentFloor studies tool use by small open-weight models. [AgentRobustBench, arXiv 2605.11928](https://arxiv.org/abs/2605.11928) · [AgentFloor, arXiv 2605.00334](https://arxiv.org/abs/2605.00334)

Other related work covers unreliable tool environments and recovery in UndoBench. The tool-eval-bench project has a scenario with an empty search result. [arXiv 2606.25819](https://arxiv.org/abs/2606.25819) · [UndoBench, arXiv 2610.05622](https://arxiv.org/abs/2610.05622)
