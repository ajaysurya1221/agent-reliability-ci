# Log-signals study: result

## First reported half

In 423 Codex sessions from 33 repositories, inside the same repository, the weighted rank agreement between the share of responses whose recorded reasoning-token count is 0 and the share of changed lines attributed to the agent was **-0.029** (21 repositories carried weight, 387 units of weight). Inside repository-and-month blocks it was -0.040. Inside repository, model-name and session-length blocks it was -0.067. 12 of the 21 repositories had a number above 0, 9 below 0 and 0 exactly 0; those above 0 carry 58% of the weight. Leaving out one repository at a time moves the first number between -0.05 and -0.01. No inferential test is applied to the paired data, because neither candidate test passed every required calibration case. This describes two records attached to the same session. It is not a cause, not a prediction, not a measure of quality, and it says nothing about order in time.

### Printed numbers

**first measure (`no_reasoning_share`)**

- Repository blocks: `rho_bar` -0.029; 21 weight-carrying repositories; 387 units of weight; 408 sessions inside weight-carrying blocks.
- Repository-and-month blocks: `rho_bar` -0.040; 21 weight-carrying repositories; 371 units of weight; 403 sessions inside weight-carrying blocks.
- Repository, model-name and session-length blocks: `rho_bar` -0.067; 16 weight-carrying repositories; 295 units of weight; 338 sessions inside weight-carrying blocks.

- Sign count: 12 repositories above 0, 9 below 0, 0 exactly 0; those above 0 carry 58% of the weight.
- Leave-one-out range: -0.05 to -0.01.
- Without the repositories that share an identified user with the other half: +0.00.

**second measure (`reasoning_tokens`)**

- Repository blocks: `rho_bar` +0.010; 21 weight-carrying repositories; 387 units of weight; 408 sessions inside weight-carrying blocks.
- Repository-and-month blocks: `rho_bar` -0.022; 21 weight-carrying repositories; 371 units of weight; 403 sessions inside weight-carrying blocks.
- Repository, model-name and session-length blocks: `rho_bar` +0.011; 16 weight-carrying repositories; 295 units of weight; 338 sessions inside weight-carrying blocks.

### Printed as checks

| Check | Found | Registered | Verdict |
|---|---|---|---|
| `sessions` | 423 | 423 | same |
| `repositories` | 33 | 33 | same |
| `outcome_at_0` | 79 | 79 | same |
| `outcome_at_100` | 228 | 228 | same |
| `outcome_between` | 116 | 116 | same |
| `first_measure_exactly_0` | 25 | 25 | same |
| `month_2026-04` | 102 | 102 | same |
| `month_2026-05` | 76 | 76 | same |
| `month_2026-06` | 109 | 109 | same |
| `month_2026-07` | 104 | 104 | same |
| `month_2026-08` | 25 | 25 | same |
| `month_2026-09` | 7 | 7 | same |

- Sessions that took the month label `unknown`: 0.
- Sessions that took the model name `unknown`: 6.

### Yardstick table

**Yardstick table (simulated, not counted; fixed now; not recomputed, extended or trimmed after the result).**

**Do not read significance from this table. Comparing the published number with these means or spreads is not a test and supports no statement that the number is, or is not, larger than chance.** The table shows only that the number moves by itself when no link is built in between a session's two numbers, and by how much in ten simulated cases. From the round 3 reviewer's implementation unless marked.

| Simulated case | Mean of `rho_bar` | SD of `rho_bar` | Data sets |
|---|---|---|---|
| Sessions independent (round 2, three implementations) | +0.00 | 0.05 | 3,000 |
| Moderate dependence in time (AR(1) 0.6) | +0.00 | 0.07 | 2,000 |
| Strong dependence in time (AR(1) 0.9), round 2 | -0.00 | 0.11 | 1,000 |
| Long constant runs, mean 15 sessions | -0.00 | 0.11 | 2,000 |
| Calendar drift shared by all repositories, 0.3 of the variance | +0.00 | 0.07 | 2,000 |
| The same at 0.6 of the variance | -0.01 | 0.17 | 2,000 |
| One shared level per calendar month | -0.00 | 0.09 | 2,000 |
| Every repository spread over the whole window, drift 0.3 | -0.01 | 0.19 | 1,000 |
| One shared break date in each number, as coded | +0.02 | 0.06 | 2,000 |
| One dated event that moves both numbers at once | +0.09 | 0.08 | 1,000 |

"AR(1) 0.6" means each session's value leans on the one before it with weight 0.6. The rule applies to nine null cases of round 3. The first row is the round 2 run of one of them (independent sessions). The third row is a round 2 case that is not among the nine. The eighth and the tenth rows are round 3 cases outside the nine. The tenth is a shared cause, not a session-level link: one dated change that affects both records puts the number near +0.09. The ninth row is one of the nine, but it has a coding fault found in review (the break had a fixed direction in both numbers); it is kept because it was measured.

### Limits that are printed with the result

General limits, printed for both halves:

1. The first number is a weighted average, and a few large repositories hold most of the possible weight (see the facts of each half). Realized contributing weights may differ from the possible weights.
2. Most sessions sit at an outcome endpoint (see the facts of each half), so many sessions share the same outcome value.
3. Many sessions carry no user id (see the facts of each half). Blocking by repository does not separate differences between people from the number.
4. The halves are not independent: 7 user ids appear in both.
5. All sessions fall between April and September 2026. A shared change over those months in both numbers moves the first number with no session-level link.
6. The first measure's denominator is the session length. A pattern carried by length cannot be separated from it here.
7. The population is conditional on the reader finding 20 countable responses: 855 of 1,444 Codex pool sessions.
8. The size gate of the brief (at least 1,000 eligible sessions in at least 30 repositories, both tools together) passed with 1,171 sessions in 104 repositories. 316 of them are Claude Code sessions that are not analysed. The analysed Codex population is 855 sessions in 65 repositories. The gate is a floor for feasibility, not a statement of power.
9. Each half's separate counts were inspected before the first registration was written, and more signal-side counts were made before this one (next section). The block definitions, the floors and the sentence were chosen knowing the first set. After the second set, two readings inside the third block definition were written down; nothing else in them was changed.
10. The yardstick table is all that is known about how large this number gets with no session-level link, and it is simulated.

Facts of the first reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 307 of the 423 sessions sit at an outcome endpoint (79 at 0%, 228 at 100%).
- 168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without one and hold about seven tenths of the possible weight (whether the four largest repositories are among these 11 was not counted); 4 repositories have no identified user.
- No repository shows two or more identified user ids: 29 show one and 4 show none.
- The 7 shared user ids hold 62 of the 423 sessions, in 11 repositories (whether these are the 11 of the line above was not counted).

## second reported half, run after the first result was committed

In 432 Codex sessions from 32 repositories, inside the same repository, the weighted rank agreement between the share of responses whose recorded reasoning-token count is 0 and the share of changed lines attributed to the agent was **+0.041** (24 repositories carried weight, 391 units of weight). Inside repository-and-month blocks it was +0.017. Inside repository, model-name and session-length blocks it was +0.085. 14 of the 24 repositories had a number above 0, 10 below 0 and 0 exactly 0; those above 0 carry 74% of the weight. Leaving out one repository at a time moves the first number between +0.00 and +0.06. No inferential test is applied to the paired data, because neither candidate test passed every required calibration case. This describes two records attached to the same session. It is not a cause, not a prediction, not a measure of quality, and it says nothing about order in time.

### Printed numbers

**first measure (`no_reasoning_share`)**

- Repository blocks: `rho_bar` +0.041; 24 weight-carrying repositories; 391 units of weight; 415 sessions inside weight-carrying blocks.
- Repository-and-month blocks: `rho_bar` +0.017; 23 weight-carrying repositories; 362 units of weight; 398 sessions inside weight-carrying blocks.
- Repository, model-name and session-length blocks: `rho_bar` +0.085; 22 weight-carrying repositories; 310 units of weight; 365 sessions inside weight-carrying blocks.

- Sign count: 14 repositories above 0, 10 below 0, 0 exactly 0; those above 0 carry 74% of the weight.
- Leave-one-out range: +0.00 to +0.06.
- Without the repositories that share an identified user with the other half: -0.02.

**second measure (`reasoning_tokens`)**

- Repository blocks: `rho_bar` -0.023; 24 weight-carrying repositories; 391 units of weight; 415 sessions inside weight-carrying blocks.
- Repository-and-month blocks: `rho_bar` -0.015; 23 weight-carrying repositories; 362 units of weight; 398 sessions inside weight-carrying blocks.
- Repository, model-name and session-length blocks: `rho_bar` -0.057; 22 weight-carrying repositories; 311 units of weight; 367 sessions inside weight-carrying blocks.

### Printed as checks

| Check | Found | Registered | Verdict |
|---|---|---|---|
| `sessions` | 432 | 432 | same |
| `repositories` | 32 | 32 | same |
| `outcome_at_0` | 107 | 107 | same |
| `outcome_at_100` | 184 | 184 | same |
| `outcome_between` | 141 | 141 | same |
| `first_measure_exactly_0` | 18 | 18 | same |
| `month_2026-04` | 84 | 84 | same |
| `month_2026-05` | 116 | 116 | same |
| `month_2026-06` | 80 | 80 | same |
| `month_2026-07` | 40 | 40 | same |
| `month_2026-08` | 72 | 72 | same |
| `month_2026-09` | 40 | 40 | same |

- Sessions that took the month label `unknown`: 0.
- Sessions that took the model name `unknown`: 0.

### Limits that are printed with the result

General limits, printed for both halves:

1. The first number is a weighted average, and a few large repositories hold most of the possible weight (see the facts of each half). Realized contributing weights may differ from the possible weights.
2. Most sessions sit at an outcome endpoint (see the facts of each half), so many sessions share the same outcome value.
3. Many sessions carry no user id (see the facts of each half). Blocking by repository does not separate differences between people from the number.
4. The halves are not independent: 7 user ids appear in both.
5. All sessions fall between April and September 2026. A shared change over those months in both numbers moves the first number with no session-level link.
6. The first measure's denominator is the session length. A pattern carried by length cannot be separated from it here.
7. The population is conditional on the reader finding 20 countable responses: 855 of 1,444 Codex pool sessions.
8. The size gate of the brief (at least 1,000 eligible sessions in at least 30 repositories, both tools together) passed with 1,171 sessions in 104 repositories. 316 of them are Claude Code sessions that are not analysed. The analysed Codex population is 855 sessions in 65 repositories. The gate is a floor for feasibility, not a statement of power.
9. Each half's separate counts were inspected before the first registration was written, and more signal-side counts were made before this one (next section). The block definitions, the floors and the sentence were chosen knowing the first set. After the second set, two readings inside the third block definition were written down; nothing else in them was changed.
10. The yardstick table is all that is known about how large this number gets with no session-level link, and it is simulated.

Facts of the second reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 291 of the 432 sessions sit at an outcome endpoint (107 at 0%, 184 at 100%).
- 101 of the 432 sessions carry no user id.
- Some of the 32 repositories show two or more identified user ids.
- The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.
