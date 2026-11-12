# Adoption signals for v2.0.0

Thresholds fixed before launch (PLAN.md phase 6): day 7, at least 25 stars and 300 unique
visitors; day 30, at least 100 stars and 3 issues or discussions opened by other people.
Day 30 missing both: feature work stops and a retrospective is written.

Public counters only. Unique visitors come from GitHub's 14-day traffic window.

| Day | Date | Stars | Forks | Open issues | Traffic | Clones | PyPI downloads |
|---|---|---|---|---|---|---|---|
| 0 (release, nothing posted yet) | 2026-11-12 | 0 | 0 | 0 | 24 views, 13 unique visitors (last 14 days) | 248 clones, 58 unique | last_day 12, last_week 121, last_month 0 |

## Launch log

- 2026-11-12: GitHub release page for v2.0.0 published (https://github.com/ajaysurya1221/agent-reliability-ci/releases/tag/v2.0.0).
- 2026-11-12: posted to r/LangChain by the maintainer (account u/Own_Task_7982), flair "Projects", title "I put create_agent behind a fault-injecting regression gate, pre-registered a test, and my own prediction lost". Body: `launch/reddit-body.md`. The first attempt was refused by Reddit's parser; the table and code formatting were removed.
- Hacker News: Show HN refused on 2026-11-12 because the account is new to the site. Not posted. To retry after the account has a comment history.
- Day counting for the thresholds starts 2026-11-12, the day of the first post, so the scheduled snapshots (19 Nov, 26 Nov, 12 Dec) stand as they are.
- 2026-11-13: correction added to `study/RESULT.md` after a reader's comment on the Reddit thread: run 1 measured wrong first tool calls in a set-up where they were fatal, not a general capability gap. A second pre-registered run follows.
- 2026-11-13: run 2 (tool errors returned to the model, pre-registered at `6fbdb1c`) ended INCONCLUSIVE after 5 rounds: baseline 480 of 480, candidate 428 of 480. Written expectation was INCONCLUSIVE. Result: `study/RESULT-run-2.md`.
