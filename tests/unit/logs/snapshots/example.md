Example data, generated. Not anyone's logs.

**Claude Code · model-1 · effort high · main thread · days at UTC+00:00 · REAL DROP**

measure, median day           | before (days) | after (days) | change  | finding
----------------------------- | ------------- | ------------ | ------- | -----------------------
reasoning tokens per response | 986 (42)      | 529 (14)     | -46%    | real drop
responses with no reasoning   | 15.0% (42)    | 15.0% (14)   | 0.0 pts | no drop (margin 10 pts)
file edits that failed        | 10.0% (42)    | 10.0% (14)   | 0.0 pts | no drop (margin 3 pts)

split 2026-11-01 · client versions 1 before, 1 after, 1 in both · working directories 1 before, 1 after · sub-agent share 0.7% -> 0.7%

One person's logs. Evidence of movement toward worse in a recorded measure; this establishes no cause and says nothing about answer quality.

Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this tool and one comparison, if the days in the window are interchangeable when nothing changes and the assumptions below hold; when days resemble their neighbours or work comes in phases the self-check measured wrong REAL DROP up to 18.1% (14 days after, 16 before) in its tested cases. Assumptions, unchecked: no date, model, effort or project chosen from these logs; a uniform shift the measure can take; the same days, setting, reference value and earlier-day values in use. Repeated checking until a result appears is not covered. arci-logs/2, digest bc3c83e31e99. Yours: uvx --python 3.14 realornoise

**Codex · model-1 · effort high · main thread · days at UTC+00:00 · NO DROP**

measure, median day             | before (days) | after (days) | change  | finding
------------------------------- | ------------- | ------------ | ------- | -----------------------
reasoning tokens per response   | 984 (42)      | 962 (14)     | -2%     | no drop (margin 25%)
responses with no reasoning     | 15.0% (42)    | 15.0% (14)   | 0.0 pts | no drop (margin 10 pts)
reasoning at one repeated value | 11.8% (42)    | 11.8% (14)   | 0.0 pts | no drop (margin 10 pts)

split 2026-11-01 · client versions 2 before, 2 after, 2 in both · working directories 2 before, 2 after · sub-agent share 0.7% -> 0.7%

One person's logs. No recorded measure moved toward worse by its margin; this does not say anything improved.

Wrong REAL DROP and wrong NO DROP are each at most 2.5% for this tool and one comparison, if the days in the window are interchangeable when nothing changes and the assumptions below hold; when days resemble their neighbours or work comes in phases the self-check measured wrong REAL DROP up to 18.1% (14 days after, 16 before) in its tested cases. Assumptions, unchecked: no date, model, effort or project chosen from these logs; a uniform shift the measure can take; the same days, setting, reference value and earlier-day values in use. Repeated checking until a result appears is not covered. arci-logs/2, digest b267f6b674a9. Yours: uvx --python 3.14 realornoise
