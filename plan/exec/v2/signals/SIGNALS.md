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
- 2026-11-14: v2.1.0 released (PR 19 merged as `5f4b8ac`, tag `v2.1.0`, PyPI files match the release workflow's `SHA256SUMS`): tool outcomes in suite reports, a clean model swap in the quickstart, both study runs and the correction in `docs/results/order-desk-study.md`, new README first screen. Prompted by the two reader comments and a deep-research round whose unlinked claims were checked first. GitHub release page and the r/LocalLLaMA post (`launch/localllama-run2.md`) not yet published.
- 2026-11-14: GitHub release page for v2.1.0 saved as a draft with the notes filled in; publishing was refused to the agent, so it waits for the maintainer's click. Merged branches `v2.1/integration` and `sprint/v2.1-integration` deleted. Reddit is not reachable by the agent's tools: the r/LocalLLaMA post and the three r/LangChain replies (`launch/langchain-replies.md`) wait for the maintainer.
- 2026-11-14: GitHub release page for v2.1.0 published by the maintainer and marked latest (https://github.com/ajaysurya1221/agent-reliability-ci/releases/tag/v2.1.0). The three unused environments were removed by the maintainer. Still waiting: the r/LocalLLaMA post and the three r/LangChain replies.
- 2026-11-14, correction to the two lines above: the three r/LangChain replies were already posted by the maintainer on 13 Nov, before v2.1.0 (seen in the maintainer's saved copy of the thread, 14 Nov 12:47; the post showed 1.7K views, 2 upvotes and 13 comments). The agent's log had missed that. The thread has since gained two unanswered comments (u/Significant_Tune9219 asking for failures by category; a question whether the 4B model met the PASS rule on the rerun) and a side thread on faults firing twice in a retry loop. New drafts for those: `launch/langchain-replies.md`.
- 2026-11-14, about 13:40: the maintainer posted replies A, B and C from `launch/langchain-replies.md` in the r/LangChain thread (seen in the saved copy of 13:42: A under u/Significant_Tune9219's "Thanks for rerunning it", B under "did the 4B clear your original PASS rule", C under u/Ludynia_Keyko). Reddit showed the hyphen lists as separate lines and turned "2.1.0" into a link. The post still showed 1.7K views, 2 upvotes, 13 comments. Not yet posted: `launch/localllama-run2.md`.
- 2026-11-14: r/LocalLLaMA refused the post. Its automatic message to u/Own_Task_7982: new members must first take part in comments and earn at least 5 karma before they can post. Same cause as the Show HN refusal on 12 Nov: the account has no history on the site. Not posted.
