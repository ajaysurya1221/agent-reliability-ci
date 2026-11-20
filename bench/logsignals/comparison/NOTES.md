# Blind implementation notes

Built from `PREREGISTRATION.md` and `INTERFACE.md` only. Every place where those two texts did
not fix exactly what to do is listed below with the words I read and the choice I made. Nothing
here states a cause, a prediction or a measure of quality.

## Ambiguities and the choice made

1. **A session whose outcome is missing.** The text says "All eligible sessions enter. No
   trimming, no transformation, no deletion", and `INTERFACE.md` still carries a check
   `outcome_missing` and an `agent_percentage` that may be "empty when missing". A missing value
   has no midrank. **Choice:** such a session is counted in the half's `sessions` and
   `repositories` and in `outcome_missing`, and is left out of every block; so "at least 2
   sessions" and `w_b = n_b - 1` are counted after dropping it. The real population is said to
   have none missing ("First half, outcome alone: ... none missing"), so on the real data this
   choice has no effect.
2. **A signal path with no row in `outcome.tsv`.** `INTERFACE.md` says `outcome.tsv` holds "one
   row per pool session (more rows than `signal.tsv`)", so every eligible path should be there.
   **Choice:** an absent path is handled exactly like an empty `agent_percentage` (missing).
3. **Which sessions the session-length thirds are cut from.** "Sort its `n` sessions by `d`"
   and "The thirds are the same for both measures". It is not said whether a session with no
   outcome occupies a position. **Choice:** the thirds are cut from every eligible session of
   the half, before the outcome side is consulted; a missing-outcome session holds its position
   and then drops out of the block.
4. **The one square root.** "The sums inside `rho_b` are made in exact rational arithmetic, with
   one square root in floating point at the end." The place of the division is not fixed.
   **Choice:** the exact rational `numerator^2 / (spread_x * spread_y)` is formed, converted to
   float once, `math.sqrt` taken once, and the sign of the exact numerator applied. When the
   exact numerator is 0 the result is exactly `0.0` and no square root is taken, which is what
   makes the "exactly 0" sign count well defined. A cross-check with a plain float
   mean-centred Pearson agreed to about 6e-17 on the planted set.
5. **Pearson's form.** Only "Pearson's correlation of the two midrank vectors" is given.
   **Choice:** `n*Sxy - Sx*Sy` over `sqrt((n*Sxx - Sx^2)(n*Syy - Sy^2))`, all sums exact. It is
   algebraically the mean-centred form; the short Spearman form the text forbids is not used.
6. **Midranks.** "tied values all take the mean of the ranks they span" — the base of the ranks
   is not stated. **Choice:** ranks 1..n ascending. Pearson is unchanged by an affine shift of
   the ranks, so a 0-based choice would give the same `rho_b`.
7. **A block whose midrank vector is constant.** Excluded by the weight rule ("neither the
   signal nor the outcome is constant inside it"), so the zero denominator cannot arise. My code
   raises rather than returning a number if it ever did.
8. **`m`, `W` and `sessions` when the floor is not met.** The registration says "every number of
   that definition for that measure is replaced by exactly `not formed (k repositories, W
   units)`", while `INTERFACE.md` says `m`, `W` and `sessions` are reported "whether or not it
   is formed" and that "When `formed` is false, `rho_bar` is `null`". **Choice:** I follow
   `INTERFACE.md` for the full-precision object: only `rho_bar` becomes `null`.
9. **The floor read as inclusive.** "at least 10 repositories carry weight and its `W` is at
   least 150" → `m >= 10 and W >= 150`. "printed only when at least 11 repositories carry
   weight" → `m >= 11` for the leave-one-out range. "only when at least 10 repositories still
   carry weight and `W` is still at least 150" → `m >= 10 and W >= 150` after the removal.
   `sets/edge_ten` sits on the boundary with `W` exactly 150 and is treated as formed.
10. **Nulling the headline section.** "every value of `first_measure_repository` that is a
    number is `null` and the two `*_formed` values are false." The sign counts `above`, `below`
    and `zero` are numbers. **Choice:** they are `null` too, and `positive_weight_share` with
    them.
11. **Which half's sessions define "shared users".** "`rho_bar` recomputed without every
    repository that holds a session whose user id also appears in an eligible Codex session of
    the other half." **Choices:** (a) the other half's id set is taken from that half's eligible
    sessions with a non-empty `user_key`; (b) an empty `user_key` never matches anything ("168
    of the 423 sessions carry no user id"); (c) a repository is removed if *any* of its sessions
    in this half carries such an id, whether or not that session has an outcome; (d) the removal
    is by whole repository, and the `rho_r` of the repositories kept are unchanged — only `T`
    and `W` are re-summed over them.
12. **"at least 10 repositories still carry weight"** is counted over the repositories that
    remain after the removal, not over the original set.
13. **The `months` check.** "the six month counts" and, separately, "how many sessions took the
    month label `unknown`". **Choice:** the `months` object holds only the `YYYY-MM` labels that
    occur, each with its count; `unknown` is never a key there and is reported only as
    `month_unknown`. A month with no session is absent rather than present with 0.
14. **An empty `model` or `month` field.** `INTERFACE.md` writes `model` as "the session's model
    name ... or `unknown`" and `month` as "`YYYY-MM`, or empty (then the label is `unknown`)".
    **Choice:** for `model` I accept both the literal string `unknown` and an empty field, and
    treat both as the name `unknown`; `model_unknown` counts sessions whose resolved name is
    `unknown`. The "most frequent model name, a tie goes to the name that sorts first" rule is
    not re-derived here, because the interface hands the resolved name over.
15. **`outcome_between`.** "outcome sessions at 0%, at 100% and between". **Choice:** strictly
    between, `0.0 < value < 100.0`, and the two endpoint counts use exact float equality with
    `0.0` and `100.0` ("used as the table gives it").
16. **`first_measure_exactly_0`.** "sessions with a first measure of exactly 0" → the exact
    fraction `zero / d` equals 0, i.e. `zero == 0`.
17. **`positive_weight_share`.** "their weight divided by the whole `W`". **Choice:** formed as
    an exact rational of two integers and converted to float once, so it does not depend on a
    summation order.
18. **`sessions` inside weight-carrying blocks.** "the number of sessions inside weight-carrying
    blocks" — per definition and measure. **Choice:** the sum of `n_b` over the weight-carrying
    blocks of that definition and measure, counting only sessions that are in a block (so not
    the missing-outcome ones, see 1).
19. **Order.** "`T` is summed with `math.fsum`, so the order of the blocks does not matter." I
    use `math.fsum` for `T` and for the `T` of the without-shared-users number. The
    leave-one-out minimum and maximum are taken over the weight-carrying repositories only.
20. **A single-session repository-and-model group.** "Positions 1 to `floor(n/3)` are the low
    third ... An empty third forms no block." With `n = 1` both `floor(n/3)` and `floor(2n/3)`
    are 0, so the one session lands in the high third and forms a block of one, which carries no
    weight. `n = 2` gives an empty low third, one middle and one high session. `sets/edge` has a
    repository with model groups of sizes 1 to 7 so every one of these cases occurs.
21. **The second measure.** "Printed for the repository blocks of the first measure only."
    **Choice:** `reasoning_tokens` gets the same three definitions and the same floor, and no
    `first_measure_repository` section; the section is computed from `no_reasoning_share` and the
    `repository` definition, and `INTERFACE.md`'s `<measure>` order confirms
    `no_reasoning_share` is the first measure.
22. **Which rho counts as "exactly 0".** "How many weight-carrying repositories have `rho_r`
    above 0, below 0 and exactly 0" — a float comparison with `0.0`. With the exact numerator
    this happens only when the exact rational numerator is 0; `sets/edge` contains one such
    repository, built on purpose.
23. **Time comparison.** "Times are compared as instants (parse them; do not compare the
    strings)" and "a session without one sorts after those with one". **Choice:**
    `datetime.fromisoformat`, and the sort key puts a present time before an absent one, with
    the path breaking any remaining tie.
24. **Top-level `repositories`.** "the eligible Codex sessions of that half and the repositories
    they sit in" — every repository holding at least one eligible session of the half, whether
    or not it carries weight.
25. **`W` when no block carries weight.** Not addressed. **Choice:** `m = 0`, `W = 0`,
    `sessions = 0`, `formed` false, `rho_bar` `null`, and no division is attempted.
    `sets/edge_few9` (discovery half) has this for the third definition.

## Choices in the simulated data (not readings of the text)

These are properties of my own `make_sets.py`, not of the registration.

- The outcome is drawn mostly at an endpoint (about 0.9 of sessions in the ordinary
  repositories) and otherwise as `100 * k / den` with `den` between 8 and 120. Session lengths
  `d` are drawn from a fixed list with a minimum of 20, and the first measure is `zero / d`.
- In `sets/planted` the first measure and the outcome are both drawn from one latent value per
  session; in `sets/none` the outcome is drawn from an independent latent. The two sets share
  `signal.tsv` byte for byte, so only the outcome column differs.
- The second measure (`reasoning_tokens`) is drawn independently of the outcome in every set;
  nothing was planted into it.
- After drawing, each repository meant to carry weight is checked and, if a value came out
  constant, one session's value is moved by the smallest step. Deliberately constant
  repositories are exempt. This keeps the planned block counts exact (for example `W` exactly
  150 in `sets/edge_ten`) instead of depending on a draw.
- Seeds are fixed constants in `make_sets.py`. Reruns of `make_sets.py` and `blind_impl.py`
  produce byte-identical files (24 files checked by SHA-256).

## What each set covers

| Set | What it holds |
|---|---|
| `sets/planted` | 25 repositories (14 confirmation, 11 discovery), mixed sizes, both halves, 3 user ids in both halves, 1 or 2 models per repository, 2 months per repository, a latent shared by the first measure and the outcome |
| `sets/none` | the same structure and the same `signal.tsv`, outcome drawn independently |
| `sets/edge` | a signal-constant repository, an outcome-constant repository, two one-session repositories, a repository with model groups of sizes 1 to 7 and tied `d`, heavy ties in both numbers, a repository with endpoints only, a session with model `unknown`, one with an empty month, four with an empty `first_time`, one with a missing outcome, a repository whose `rho_r` is exactly 0, a shared user id, and a discovery half that meets no floor |
| `sets/edge_few9` | 9 weight-carrying repositories, `W` 155: the repository floor of the first measure fails on the repository count while the second measure's does not |
| `sets/edge_ten` | exactly 10 weight-carrying repositories and `W` exactly 150: formed, but the leave-one-out range is not formed; no shared user id, so the without-shared number is formed |
| `sets/edge_eleven` | exactly 11 weight-carrying repositories, `W` 151: the leave-one-out range is formed, and two shared-user repositories drop the without-shared number below both floors |
