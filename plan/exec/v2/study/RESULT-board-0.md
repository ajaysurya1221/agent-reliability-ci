# Result, benchmark Board-0: all five registered criteria hold (K1 and K2 on day 1, K3 and K4 across both days, K5 on the evidence file)

## Read this first

- The question: when a lookup comes back empty, does a small local model still finish the task?
- Five local models answered order and calendar questions on two days, on one laptop.
- Every task was run in two ways. In one the empty result was passed on as it was. In the other it was replaced by one sentence telling the model to repeat the lookup.
- Three models (Qwen 3.5 4B, Gemma 4 12B, Llama 3.1 8B): across the two days they passed 84% to 100% of measured trials with the sentence and 0% to 13% with the empty result. Gemma passed 11 of 16 calendar trials with the sentence on day 1.
- One model (Qwen 2.5 7B) went the other way on both days: it passed more tasks with the empty result than with the sentence.
- One model (Mistral NeMo 12B) passed no task in either way. Its PASS is a tie at zero, and on day 2 it also fell short on the warm-up calendar tasks.
- The grade is on the final answer. Repeat lookups that returned the record are counted separately (`retrieved`). On day 2, Llama passed one empty-result trial without retrieving the record.
- The opening lookup is scripted. This says nothing about hosted models, larger models or real agents, or about how often an empty result happens in use.
- An agent that read no write-up counted the runs again from the raw files and graded all 992 trials again. Every grade and every count it produced matches.

## Registration and amendments

Board-0 was registered on 27 November 2026 before any model saw a Board task in this study. Both days used Ollama 0.32.14 with a 32768-token context, temperature 0.7 and reasoning off. The harness sent one request at a time and supplied no sampling seed. The two days used different task seeds fixed in advance. [Registration and amendments](board-0/PREREGISTRATION-board-0.draft.md) · [Model tags and digests](board-0/models.json)

**Amendment 1 corrected the pin after the initial results were known.** The pin tested whether a model could call a toy tool and read back a random token. In slot order, the initial scores were 20/20, 20/20, 8/20, 7/20 and 0/20. The amendment removed the prefix `pebble-` from the tool’s reply, leaving 24 random lowercase hexadecimal characters. It kept the question, tool, grading, 16/20 threshold and two empty-reply checks. Before any corrected probe or Board task, the amendment committed to testing all five models once on the corrected pin and using those results for admission.

**Amendment 2 applied the spare rule before any clean run.** The corrected scores for M1 through M5 were 20/20, 20/20, 20/20, 18/20 and 0/20. The original M5, `granite3.3:8b-ctx32k`, made no native tool call in those probes. Spare S1, `qwen2.5:7b-ctx32k`, scored 20/20 and took M5 on both days. Spare S2, `llama3.2:3b-ctx32k`, did not run. The harness wrote the final roster and regenerated M5’s 34 run descriptions. The other 136 were byte-identical. The pin counts here were checked against the stored pin files in `board-0/pins/`.

## Criteria

This is the orchestrator’s reading of the two-day report. BLOCK means the empty arm scored worse than the sentence arm by more than the registered margin of ten percentage points. PASS means it was within that margin or did better. A decision requires a rated model-day, a statistical PASS or BLOCK, and reading conditions R1 through R4. The numbers are those printed by the registered report (`sh harness/run-board0.sh report`), which is the file `result.md` inside the evidence zip and in `board-0/`.

| Criterion | Reading | Arithmetic |
|---|---|---|
| K1. Reach beyond M1 | Holds | Two of M2 through M5 gave BLOCK on day 1 (M2 and M3). On M2 the gap in orders was 16/16 − 0/16 = 100 percentage points. In calendar it was 11/16 − 1/16 = 62.5 points. Both exceed 20 points. |
| K2. Different outcomes with a capable empty arm | Holds as written | M1, M2 and M3 gave BLOCK on day 1. M5 gave PASS. Its empty arm passed 16/16 orders (100%) and 14/16 calendar tasks (87.5%). Each meets 75%. M4’s zero tie does not qualify for K2. |
| K3. Same decision on both days | Holds | No PASS flipped to BLOCK or vice versa. M1, M2, M3 and M5 repeated their decisions. That is 4/5 = 80%, the required four. M4’s unrated day 2 contributes no decision. |
| K4. Decisions and elapsed time | Holds | Five decisions on day 1 plus four on day 2 = 9/10, above the required 7/10. Across all ten model-days the median combined clean and measured time was **127.76 seconds**, below the 60-minute limit. |
| K5. Offline evidence check | Holds | A fresh agent must use the evidence zip, its separately published digest, the study checker and released ARCI offline. It must reproduce 10/10 stored verdicts, regrade every trial and reject 3/3 altered copies (one changed grade, rule or decision). |

**K5, as checked.** The evidence file is `board0-evidence.zip` (1,941 files; SHA-256 `35f70d9b3a787a1e429fd623dd550b80d77b99da60ea7ce2291d74d9204e5340`). A fresh agent, offline, was given that file, its digest file, the study's verifier and the released ARCI 2.4.1, and nothing else.

- Its first attempt failed: the verifier calls the released `arci` command by name and the command was not on the search path. With the released command's folder added to the path the verifier accepted the file: "10 measured suites and 10 clean rows matched; corrected pins and Board trials regraded".
- That reproduces 10 of 10 stored verdicts (`stored decision: MATCH` for each) and regrades every trial. The verifier prints no trial count; the file holds 992 trial records (672 measured, 320 clean).
- Three altered copies, each with its own freshly computed digest so that the digest could not be the reason, were all rejected: one changed grade ("trial grade"), one changed rule (threshold 40 changed to 41: "descriptor rule"), one changed verdict (BLOCK changed to PASS: "published audit figures differ").
- The unaltered file with a digest wrong in one character was rejected too ("zip digest").
- The orchestrator repeated the check of the original and of one altered copy with the same outcome.

A run counts under the following conditions.

- **R1.** The registration and digests for the inputs and run descriptions must have been pushed before the runs. The model digest, server version and context must match at admission.
- **R2.** Every scheduled trial through the stopping round must have one ledger entry and one receipt. The opening lookup must return the seeded record, and the model must receive its arm’s assigned text.
- **R3.** No crash is allowed. At most 5% of either arm’s trials may hit the 120-second limit.
- **R4.** The gate must report `stored decision: MATCH`, the audit must be clean and the two independent counts must agree.

The run logs record matching counts for all 20 scheduled runs and `stored decision: MATCH` for each of the ten measured runs.

**Independent recount.** An agent that was given only the raw files (trial records, stored decisions, ledgers, receipts, run descriptions, the task list, the two worlds and the grading rule) and read no write-up and no count file counted the runs again with `jq`. For all ten measured runs its trials, passes per arm and family, pair signs, stopping rounds, stored verdicts and ratings equal the report's. It graded all 992 trials again from the raw final texts (672 measured, 320 clean): every grade matched the stored one. The agent also wrote a Python version that it could not run in its sandbox; the orchestrator ran it afterwards and it gave the same totals and the same per-run summaries. Every measured trial has exactly one ledger record and one receipt. All 992 trials finished within 120 seconds (R3): the longest measured trial took 4.868 seconds and the longest clean trial 5.691 seconds. Thirteen tool calls returned an application error (eleven "unknown room", two "unknown SKU"); those trials completed and no pair was errored.

## Results by day

The harness made the correct opening lookup and blanked its result. The empty arm received an empty string. The sentence arm received exactly “The lookup returned no data. Repeat the same call with the same arguments.” The model then chose what to do. Each round paired the two arms on eight order tasks and eight calendar tasks. The rule checked for a verdict after each round, up to 26 rounds.

In the tables, **sentence · empty** is the order of the two arms. Passes use the registered grade. `retrieved` counts trials where a later lookup returned the target record. `exact` counts final answers equal to the key after trimming surrounding whitespace and removing one trailing period. The clean run kept the opening result. Its counts show distinct tasks passed at least once in two tries, in **orders · calendar** order. Rating required at least 6/8 in each family. Seconds cover the clean and measured runs from claim through verification. [Harness and grading rules](board-0/harness/INTERFACE.md)

### Day 1 · 27 November 2026

| Model | Verdict | Stop round | Passes | Orders | Calendar | `retrieved` | `exact` | Clean rating (orders · calendar) | Seconds |
|---|---|---:|---|---|---|---|---|---|---:|
| M1 `qwen3.5:4b-mlx-ctx32k` | BLOCK | 1 | 16/16 · 1/16 | 8/8 · 1/8 | 8/8 · 0/8 | 16 · 1 | 0 · 0 | rated (8/8 · 8/8) | 98.65 |
| M2 `gemma4:12b-mlx-ctx32k` | BLOCK | 2 | 27/32 · 1/32 | 16/16 · 0/16 | 11/16 · 1/16 | 30 · 1 | 0 · 0 | rated (8/8 · 7/8) | 145.65 |
| M3 `llama3.1:8b-ctx32k` | BLOCK | 1 | 16/16 · 0/16 | 8/8 · 0/8 | 8/8 · 0/8 | 16 · 0 | 0 · 0 | rated (8/8 · 8/8) | 90.80 |
| M4 `mistral-nemo:12b-ctx32k` | PASS | 5 | 0/80 · 0/80 | 0/40 · 0/40 | 0/40 · 0/40 | 0 · 0 | 0 · 0 | rated (8/8 · 6/8) | 317.51 |
| M5 `qwen2.5:7b-ctx32k` | PASS | 2 | 11/32 · 30/32 | 2/16 · 16/16 | 9/16 · 14/16 | 11 · 30 | 0 · 0 | rated (8/8 · 8/8) | 158.06 |

### Day 2 · 28 November 2026

| Model | Verdict | Stop round | Passes | Orders | Calendar | `retrieved` | `exact` | Clean rating (orders · calendar) | Seconds |
|---|---|---:|---|---|---|---|---|---|---:|
| M5 `qwen2.5:7b-ctx32k` | PASS | 2 | 11/32 · 29/32 | 1/16 · 16/16 | 10/16 · 13/16 | 12 · 30 | 0 · 0 | rated (8/8 · 8/8) | 160.42 |
| M4 `mistral-nemo:12b-ctx32k` | PASS | 5 | 0/80 · 0/80 | 0/40 · 0/40 | 0/40 · 0/40 | 0 · 0 | 0 · 0 | not rated (8/8 · 4/8) | 319.29 |
| M3 `llama3.1:8b-ctx32k` | BLOCK | 1 | 15/16 · 1/16 | 7/8 · 0/8 | 8/8 · 1/8 | 16 · 0 | 0 · 0 | rated (8/8 · 8/8) | 90.73 |
| M2 `gemma4:12b-mlx-ctx32k` | BLOCK | 1 | 14/16 · 0/16 | 8/8 · 0/8 | 6/8 · 0/8 | 15 · 0 | 0 · 0 | rated (8/8 · 7/8) | 109.86 |
| M1 `qwen3.5:4b-mlx-ctx32k` | BLOCK | 1 | 16/16 · 2/16 | 8/8 · 2/8 | 8/8 · 0/8 | 16 · 2 | 0 · 0 | rated (8/8 · 8/8) | 95.12 |

M4 passed 0/80 trials in each arm on each day. The statistical PASS records a tie at zero. On day 1 its clean calendar score met the threshold at 6/8. On day 2 it fell to 4/8, so the stored PASS does not count as a day-2 decision.

### Pair signs

Minus means the sentence passed and the empty reply failed. Plus means the reverse. Zero means the two got the same grade. Each cell lists **minus / zero / plus / errored** pairs.

| Model | Day 1 | Day 2 |
|---|---|---|
| M1 | 15 / 1 / 0 / 0 | 14 / 2 / 0 / 0 |
| M2 | 26 / 6 / 0 / 0 | 14 / 2 / 0 / 0 |
| M3 | 16 / 0 / 0 / 0 | 14 / 2 / 0 / 0 |
| M4 | 0 / 80 / 0 / 0 | 0 / 80 / 0 / 0 |
| M5 | 2 / 9 / 21 / 0 | 3 / 8 / 21 / 0 |

## Every scheduled run

All 20 scheduled runs started once and finished, ten clean and ten measured. None was refused, missed or interrupted. Day 1 ran on 27 November 2026 from 00:56 to 01:10 IST. Day 2 ran on 28 November from 00:05 to 00:18 IST, in reverse model order. Times below are local log times. `E` marks a measured run. For each model-day the logged start-to-end total (whole seconds) is about 3 to 4.5 seconds longer than the elapsed time used for K4.

| Run | Start (IST) | End (IST) | Trials |
|---|---|---|---:|
| `board0-d1-M1-clean` | 00:56:46 | 00:57:29 | 32 |
| `board0-d1-M1-E` | 00:57:29 | 00:58:29 | 32 |
| `board0-d1-M2-clean` | 00:58:29 | 00:59:19 | 32 |
| `board0-d1-M2-E` | 00:59:19 | 01:00:58 | 64 |
| `board0-d1-M3-clean` | 01:00:58 | 01:01:41 | 32 |
| `board0-d1-M3-E` | 01:01:41 | 01:02:32 | 32 |
| `board0-d1-M4-clean` | 01:02:32 | 01:03:33 | 32 |
| `board0-d1-M4-E` | 01:03:33 | 01:07:54 | 160 |
| `board0-d1-M5-clean` | 01:07:54 | 01:08:38 | 32 |
| `board0-d1-M5-E` | 01:08:38 | 01:10:35 | 64 |
| `board0-d2-M5-clean` | 00:05:09 | 00:05:53 | 32 |
| `board0-d2-M5-E` | 00:05:53 | 00:07:53 | 64 |
| `board0-d2-M4-clean` | 00:07:53 | 00:08:58 | 32 |
| `board0-d2-M4-E` | 00:08:58 | 00:13:16 | 160 |
| `board0-d2-M3-clean` | 00:13:16 | 00:14:00 | 32 |
| `board0-d2-M3-E` | 00:14:00 | 00:14:51 | 32 |
| `board0-d2-M2-clean` | 00:14:51 | 00:15:46 | 32 |
| `board0-d2-M2-E` | 00:15:46 | 00:16:45 | 32 |
| `board0-d2-M1-clean` | 00:16:45 | 00:17:28 | 32 |
| `board0-d2-M1-E` | 00:17:28 | 00:18:24 | 32 |

## Predictions against outcomes

**Both written predictions expected K2 to miss. It held.** M5 (Qwen 2.5 7B) passed more tasks with the empty text than with the sentence. The counts were 30/32 against 11/32 on day 1 and 29/32 against 11/32 on day 2.

The consultant put the chance of a K2 miss at about 60% and the chance of all five holding at about 25%. The orchestrator also put the overall chance of a pass at about 25%. It predicted BLOCK for M1 and M2 on both days and a BLOCK among M3 through M5. Those predictions held, with M3 giving BLOCK on both days. It expected K1 and K3 to hold and K4 to hold unless two models failed the clean rating. All three criteria held, and so did K5. Both predictions had put all five holding at about 25%. The maintainer supplied no prediction before registration.

## Between the days

On 27 November at about 14:13 IST, the model server was stopped and started again for a live rehearsal of another study, Size-0. It used the same server version (0.32.14) and the same three settings. Two more model tags were downloaded for Size-0. Its day 1 ran on the same laptop and server from 17:09 to 18:08 IST.

Before Board-0 day 2, a readiness check confirmed the server version, the five registered model digests, the 32768-token context and that no other run was active. Size-0 day 2 started after Board-0’s last run ended.

## Limits

These were five small local models from four makers, all on one laptop. M1 and M5 are both Qwen models from Alibaba. The harness scripted the opening call and blanked its result. The two task families cover order totals and calendar fields. Earlier studies had used the order questions with M1 and M2. The calendar tasks were new to all five.

The grader reads the final reply when the model stops calling tools. It removes the order or event ID, then looks for the requested value. A correct value can still fail if the answer includes another value of the same type from the seeded records. Giving a full calendar record can therefore fail even when the requested field is right. Integer matches allow thousands separators. Text matches need whole words and matching case. Extra words around the right value are allowed. Even a sentence that denies the correct value can pass if it names that value and no decoy. Empty text, a timeout or no final answer within budget fails.

## Not claimed

Earlier work covers how reply wording changes recovery, recovery benchmarks on local models, empty-result tests, fault proxies and grading without a judge model. Board-0 claims no novelty for these. The registration cites arXiv 2611.11581 (how the delivery of an error changes recovery, 13 open models) and 2610.10062 (loud and quiet faults). Additional related work includes 2605.11928 (AgentRobustBench, 21 models), 2606.25819 (tool-environment unreliability), 2610.05622 (UndoBench) and 2605.00334 (AgentFloor, small open-weight models on tool use). The tool-eval-bench project already has a scenario on an empty search result. Three of the five small models date from 2024 and 2025. These results say nothing about hosted models, larger models or real agents. The scripted opening gives no estimate of how often an empty lookup occurs in use. A BLOCK gives no instruction to ship this sentence. No claim is made that anyone asked for the table. Nothing was filed on anyone else’s tracker.

## What the result allows

The registered rule stops Board work if K1, K2 or K3 misses, and the numbers are published. If the miss is confined to K4 or K5, the rule allows one registered repair and one rerun. A second miss stops the Board.

If all five hold, the rule calls for publishing the dated table, both days’ counts by family, the exact prompt and reply texts, the evidence zip and rerun instructions. An `arci board` command **may** then be built. Nothing is being built now, and the maintainer decides separately. At the 30-day check, the registration asks whether someone outside the project has run and sent in a row, or whether three outside questions about recovery have come in. Otherwise the table is frozen as a dated record.
