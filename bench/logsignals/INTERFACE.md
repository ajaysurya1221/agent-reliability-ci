# Interface note: file formats and names only

This note fixes file formats and names so that two independent implementations can be compared.
It contains no statistics. Every definition of a number comes from `PREREGISTRATION-2.md`
(sections "The two numbers per session", "What will be computed", "What will be published").

## Private input tables (UTF-8, tab separated, one header row, `\n` line ends)

`signal.tsv`, one row per eligible Codex session of either half:

| column | meaning |
|---|---|
| `path` | transcript path as written in the pool manifest; unique |
| `repo_key` | 16 lower-case hex digits |
| `half` | `confirmation` (the first reported half) or `discovery` (the second) |
| `month` | `YYYY-MM`, or empty (then the label is `unknown`) |
| `user_key` | 16 lower-case hex digits, or empty (no user id) |
| `model` | the session's model name as the registration defines it, or `unknown` |
| `d` | session length: main-thread responses with a known reasoning count (integer, at least 20) |
| `first_time` | the earliest timestamp among the session's main-thread responses, counted or not (not necessarily first in file order), ISO 8601 UTC such as `2026-05-03T14:07:09.123456+00:00`, or empty |
| `zero` | how many of the `d` responses have a count of 0 (integer); `no_reasoning_share = zero / d` exactly |
| `tokens_num`, `tokens_den` | `reasoning_tokens` as the exact fraction `tokens_num / tokens_den` (`tokens_den` is 1 or 2) |

`outcome.tsv`, one row per pool session (more rows than `signal.tsv`):

| column | meaning |
|---|---|
| `path` | as above |
| `agent_percentage` | the table's value written with `repr(float)`, or empty when missing |

Times are compared as instants (parse them; do not compare the strings).

## Full-precision description (for comparing implementations on simulated data only)

A JSON object, keys sorted, for one half:

```
{
  "half": "confirmation",
  "sessions": 0, "repositories": 0,
  "measures": {
    "<measure>": {
      "<definition>": {"formed": true, "rho_bar": 0.0, "m": 0, "W": 0, "sessions": 0}
    }
  },
  "first_measure_repository": {
    "above": 0, "below": 0, "zero": 0, "positive_weight_share": 0.0,
    "loo_formed": true, "loo_min": 0.0, "loo_max": 0.0,
    "without_shared_formed": true, "without_shared": 0.0
  },
  "checks": {
    "outcome_at_0": 0, "outcome_at_100": 0, "outcome_between": 0, "outcome_missing": 0,
    "first_measure_exactly_0": 0, "months": {"YYYY-MM": 0}, "month_unknown": 0, "model_unknown": 0
  }
}
```

- `<measure>` is `no_reasoning_share` or `reasoning_tokens`; `<definition>` is `repository`,
  `repository_month` or `repository_model_length`.
- `m` is the number of weight-carrying repositories, `W` the weight, `sessions` the number of
  sessions inside weight-carrying blocks, all for that definition and measure, whether or not it
  is formed. When `formed` is false, `rho_bar` is `null`.
- When the floor of the repository blocks of the first measure is not met, every value of
  `first_measure_repository` that is a number is `null` and the two `*_formed` values are false.
- `positive_weight_share` is a fraction between 0 and 1. All floats at full precision.
- `sessions` and `repositories` at the top are the eligible Codex sessions of that half and the
  repositories they sit in.
