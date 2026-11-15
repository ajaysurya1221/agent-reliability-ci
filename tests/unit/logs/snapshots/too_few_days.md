**Claude Code · gpt-5.3 · effort high · main thread · days at UTC+05:30 · CANNOT TELL**

measure, median day           | before (days) | after (days) | change | finding
----------------------------- | ------------- | ------------ | ------ | ------------
reasoning tokens per response | 100 (1)       | - (0)        | -      | too few days
responses with no reasoning   | 0.0% (1)      | - (0)        | -      | too few days
file edits that failed        | - (0)         | - (0)        | -      | too few days

split 2026-05-01 · client versions 2 before, 0 after, 0 in both · working directories 3 before, 0 after · sub-agent share 0.0% -> -

This setting: first response in the window 2026-04-21 · days with a response 1 before, 0 after

Claude Code deletes session files after 30 days by default (setting cleanupPeriodDays). With --keep, each day's counts are kept for later runs, for settings shown by name.

One person's logs. Not enough to tell a shift from noise.

Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this tool and one comparison, if the days in the window are interchangeable when nothing changes and the assumptions below hold; with days that resemble their neighbours the self-check measured wrong REAL DROP up to 11.8% (5 days after, 10 before) and 3.55% (7 after, 21 before) in its tested cases. Assumptions, unchecked: no date, model, effort or project chosen from these logs; a uniform shift the measure can take; the same days, setting, reference value and earlier-day values in use. Repeated checking until a result appears is not covered. arci-logs/2, digest cf89a30a2a9d. Yours: uvx --python 3.14 realornoise
