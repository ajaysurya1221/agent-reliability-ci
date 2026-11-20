# SPEC_D: calibration of the primary test under serial dependence, and of a joint baseline gate

Synthetic data only. Standard library only, `/usr/bin/python3 -I`, fixed seeds. No real data
exists for you: nothing under `~/arci-data` may be opened. Read `FACTS.md`, `design/JUDGE.md`
and `astra_design_answer.md` in the parent folder first.

## Why

A design panel chose, for a pre-registration, a within-repository test: statistic
`T = sum_r w_r * rho_r`, `w_r = n_r - 1`, `rho_r` = Spearman with midranks inside repository
`r`, published as `rho_bar = T / W`, `W = sum w_r` over repositories with `n_r >= 2` and both
numbers non-constant. Its reference distribution shuffles the signal among the sessions of one
repository (test **S**).

A consultant found a hole: sessions of one repository come in a time order. If the signal
series and the outcome series are each autocorrelated but independent of each other (no shared
trend), a shuffle test is anticonservative, because it assumes the sessions are exchangeable.
A second point: passing a length-blocked test and a model-blocked test separately does not show
that the signal adds to length and model jointly.

This calibration must (1) measure how large the hole is at these sizes, (2) compare repairs,
(3) calibrate one joint baseline gate, (4) report coverage of the interval. The result decides
what is registered. Report every number honestly, including bad ones.

## Fixed inputs

Repository sizes (33): [WITHHELD: the 33 repository session counts of the first half; disclosure rule 2 of the registration]. Sessions inside a repository have a time order
`t = 1..n_r`.

Outcome marginal: 79 of 423 at 0, 228 at 100, 116 strictly between (integers 1..99 are fine).
Signal marginal: a share `k/d` with `d >= 20`; quartiles near 0.08, 0.16, 0.26; about 6% of
sessions at exactly 0; none at 1.

## Generator (each implementer builds its own; state every choice you make)

For each repository: a repository effect on each latent (correlated 0.6 between the two
latents across repositories, variance share about 0.3), plus a within-repository latent series
for the signal `u_t` and for the outcome `v_t`. Map latents to the marginals above: the
outcome through thresholds that give the endpoint masses (per-repository endpoint mass may
vary), the signal through a monotone map to a share with a denominator `d` (the session
length, see below), rounded to `k/d`.

Within-repository series, null scenarios (the two series are independent of each other):

- **N0** independent sessions.
- **N1, N2, N3** AR(1) in both, coefficient 0.3, 0.6, 0.9.
- **N4** AR(1) 0.9 in the signal, 0.3 in the outcome.
- **N5** regimes: each series is piecewise constant plus noise, with change points drawn
  independently for the two series (mean regime length 5 sessions; noise share 0.3).
- **N6** random walk in both (independent), strongly non-stationary.

Scenarios that are NOT nulls for a within-repository estimand (report them separately, they
show what the test reacts to):

- **X1** a shared linear trend over `t` in both series in the 8 largest repositories.
- **X2** hidden people: in 11 repositories, sessions belong to one of 3 hidden people (in
  contiguous runs in time), each with an effect on both latents (correlated 0.8).

Alternatives (a real session-level link): innovations of `u_t` and `v_t` correlated
0.10, 0.18, 0.25, 0.45, once with independent sessions and once with AR(1) 0.6 in both.

## Tests to compare (same statistic `T`, two-sided, alpha 0.05)

- **S** shuffle the signal inside each repository.
- **C** circular shift: inside each repository keep both series in time order and shift the
  signal series by a uniform random offset in `0..n_r - 1` (independent offsets per
  repository). p-value `(1 + #{|T*| >= |T| - 1e-9}) / (B + 1)`; the observed arrangement is
  counted through the `1 +`.
- **F** sign flip over repositories: reference distribution `sum_r s_r * w_r * rho_r` with
  independent random signs `s_r`. Needs no exchangeability inside a repository.
- **K** block shuffle: cut each repository's time order into consecutive blocks of length
  `ceil(sqrt(n_r))` and permute whole blocks of the signal series (the last block may be
  shorter).
- You may add ONE further candidate if you can argue it is better; keep it simple.

Use B = 999 draws per test in the simulation. At least 1,000 data sets per null scenario
(Monte Carlo error about 0.007) and 400 per alternative and per X scenario.

Report, per scenario and test: the rejection rate; the mean and SD of `rho_bar`; and for the
interval `rho_bar +/- t(m-1, 0.975) * max(SE_jack, 1/sqrt(W))` (cluster jackknife over
contributing repositories) its coverage of the scenario's true mean `rho_bar` (estimate that
mean from 2,000 further data sets) and how often it lies entirely inside (-0.15, +0.15).

## Joint baseline gate

Each session also has a length `d` (main-thread responses with a known count; log-normal,
median 60, minimum 20) and a model name (1 to 3 names per repository, changing in contiguous
runs in time; about half of the larger repositories have one name only).

Gate test **J**: the same statistic computed inside blocks
`repository x model name x length tercile`, where terciles are cut inside each
`repository x model name` group (sort by length, ties by time order, cut at `floor(n/3)` and
`floor(2n/3)`; a block of one session carries weight 0). Its reference distribution is the
candidate test applied inside blocks (for C and K: the block's sessions kept in time order).
The gate "can be formed" when its total weight `W_J >= 150` and at least 10 blocks carry
weight.

Scenarios for the gate:

- **G0** null (N0 and N2).
- **G1** the link is fully carried by length: `u` depends on `log d`, `v` depends on `log d`,
  no direct link (so the primary should often reject and the gate should not).
- **G2** the link is fully carried by the model name (a per-model effect on both latents).
- **G3** a direct link (innovation correlation 0.18 and 0.25) on top of G1's length effects.

Report: how often the primary rejects, how often the gate rejects with the same sign, how
often both do (this is "an association is shown"), the distribution of `W_J`, and how often
the gate cannot be formed. Also report the alternative of two separate gates (length-only
blocks and model-only blocks, both required) for the same scenarios, so the two can be
compared.

## Checks you must run on your own code

- On a tiny data set (3 repositories of sizes 4, 3, 2) the Monte Carlo p-value of S agrees with
  full enumeration within Monte Carlo error, and the tolerance rule counts mathematically
  equal statistics as equal (build a case with tied ranks where two different arrangements
  give the same `T`).
- `Var(rho_r)` under S equals `1/(n_r - 1)` by enumeration for a small repository with ties.
- A second run with the same seed gives byte-identical output.

## Output

Write to `calib/` in the parent folder: your script(s), a results file with every table, and
`REPORT_<your label>.md` with: the tables; which tests hold alpha under which null scenarios
(a test "holds" if its rate is at most 0.065 with 1,000 data sets); power of the tests that
hold; your recommendation for the registered primary test and gate in at most 10 lines; and
what the recommended test still cannot protect against, in plain words.
