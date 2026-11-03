# Independent agent usability rehearsal

This is an agent QA exercise, not a human adoption or retention study. The
operator authorized autonomous agent assistance on 2026-11-03 after PR 15 merged.
Product revision: `417f1310cdf237712a8b9af134bfbb3a7e1f2f6f`.

Predeclared tasks (30-minute maximum for the participant): inspect three native
store comparisons, identify the first recorded tool-path change, distinguish
intentional reporting drift from proven regression, and explain the independent
statistical verdicts. Record time, commands, assistance, hashes, interpretation
errors and usability friction. Do not change any statistical design or source
store. No agents/oracles or live endpoints may execute during the reader task.

The participant is a fresh, non-author agent with no inherited chat history. It
receives the case list, command location, CLI help and recipe. The fixture source
and answer key are withheld until the initial answer. This is limited blinding:
repository documentation may describe the historical guardrail cases, and an
agent is not representative of a human cold reader.

Two cases use unchanged committed guardrail stores. One new offline fixture runs
the packaged inventory baseline and a wrapper that adds reporting metadata to its
result; its oracle, tool policy, task, environment and statistical defaults stay
unchanged. Its N=1 design is fixed before execution. An inconclusive result is
retained, never extended or rerun to obtain PASS.

Outcome rubric: correctly locate the missing call and metadata change; do not
equate DRIFT with regression or MATCH with reliability; preserve BLOCK and
INCONCLUSIVE as non-green; report raw-record inspection needed beyond default
hash/path output. Human first-use and seven-day retention remain unmeasured.
