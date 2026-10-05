# ARCI: Planning, Gating and Reproducing Agent Regressions

Technical report draft for the dated evidence package. Paths below are repository-root relative. Release identity: <<REPRO: final source commit, evidence tag, and evidence-index.json>>.

## 1. The question

A practitioner changes an agent’s prompt, retry policy, harness, or model: is the resulting difference real or noise, and what broke? Evaluation-tool maintainers face the same question when deciding what should make CI non-green.

The demand is visible in public engineering records:

- Promptfoo’s request for repeated-success measurement, opened 2025-10-16, and its linked implementation proposal show demand for consistency beyond average success: [issue #5947](https://github.com/promptfoo/promptfoo/issues/5947), [PR #8108](https://github.com/promptfoo/promptfoo/pull/8108) (both still open on 2026-10-05: the issue since 2025-10-16, the PR last updated 2026-09-16), checked 2026-10-05.
- *On Randomness in Agentic Evals*, an ICLR 2026 Agents in the Wild workshop paper, recommends independent repetitions and power analysis because apparently improved scores can reflect sampling variation: [paper, revision 2026-03-23](https://arxiv.org/html/2602.07150v2).
- Anthropic’s 2025-09-17 postmortem describes noisy evaluations that failed to expose reported degradation or connect it promptly to serving changes: [postmortem](https://www.anthropic.com/engineering/a-postmortem-of-three-recent-issues).
- Anthropic’s 2026-04-23 postmortem connects quality regressions to reasoning configuration, context handling, and prompt changes that existing checks initially missed: [postmortem](https://www.anthropic.com/engineering/april-23-postmortem).
- Anthropic’s 2026-02-05 infrastructure study shows that execution-resource configuration can change measured coding-agent performance: [infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise).

These sources motivate measurement and diagnosis; they do not establish that arci would have prevented those incidents.

## 2. What arci does differently

**The experiment contract.** A sealed manifest declares the task, arms, oracle, conditions, seeds, budgets, sample size, and decision rule before execution. The statistical rule—including `alpha`, `delta`, `interval_method`, and planned looks—enters each trial’s identity. Resealing only the manifest with a post-hoc rule produces a schedule/specification mismatch and `ERROR`. Missing, duplicated, foreign, or incorrectly sealed trials also invalidate the experiment. This detects inconsistent records under the trusted-author model; it is not external timestamping or protection against an author fabricating a consistent history. Sources: `src/arci/schema.py`, `src/arci/schedule.py`, `src/arci/gate.py`, `docs/STATISTICS.md`, `docs/TRUST_MODEL.md`.

**The exact gate.** For each of K gating conditions, the default fixed-sample rule constructs Clopper–Pearson intervals using per-arm tails `alpha/(4K)`. For candidate-minus-baseline success probability, its bounds are `L = L_B − U_A` and `U = U_B − L_A`. It returns `PASS` when `L > −delta`, `BLOCK` when `U < −delta`, and otherwise `INCONCLUSIVE`; inequalities are strict. Bonferroni supplies simultaneous coverage under the contract’s binomial assumptions. Candidate hard-invariant violations override rate comparisons; invalid experiments take precedence as `ERROR`. `INCONCLUSIVE` stays non-green without claiming a regression. `PASS` establishes relative non-inferiority within the declared margin, not absolute reliability. Sources: `docs/STATISTICS.md`, `src/arci/stats.py`, `src/arci/gate.py`.

**The fault boundary.** Python agents use a declared tool interface; command agents use a harness-owned stdio MCP boundary. A supported System One decision endpoint is recorded through the same machinery, with confidence and availability perturbations. Injected faults test agent behavior; recognized real provider, harness, or grader faults invalidate measurement. Calls that bypass these boundaries remain invisible. The trusted harness, environment, and oracle evaluate buggy agents; this is not hostile-code containment. Sources: `docs/TRUST_MODEL.md`, `docs/DECISIONS.md`, `docs/design/0002-out-of-process-boundary.md`, `docs/design/0003-decision-boundary.md`.

**The failure pipeline.** A verdict leads to a passing/failing trace comparison, normalized boundary divergence, ddmin over injected faults while preserving the failure fingerprint, and a replay bundle. Divergence locates an observable difference; it does not by itself prove causality. Replay requires exact recording consumption and matching outcome and fingerprint. “1-minimal” concerns single-fault removals under the tested deterministic setup, not a globally smallest cause. Live decision-model reductions remain “reduced,” including cases where no fault was removed; uncertain removal trials cannot establish minimality. Sources: `src/arci/diff.py`, `src/arci/minimize.py`, `src/arci/replay.py`, `docs/design/0004-day-one.md`.

## 3. Operating characteristics

The published table below gives `P(PASS) / P(BLOCK) / P(INCONCLUSIVE)` for independent binomial arms, fixed sample size, `alpha=0.05`, `delta=0.10`, and K=1. N is trials per arm. Every cell comes from `README.md`, “The gate, measured against itself”; generated values are in `docs/reports/ci-gate-2026-10-06/metrics/selfcheck-clopper_pearson.json`. Displayed probabilities are rounded, so displayed zeros need not be exact zeros.

| Assumed baseline → candidate | N=20 | N=100 | N=200 | N=400 |
|---|---|---|---|---|
| 0.95 → 0.95 | .000 / .000 / 1.000 | .443 / .000 / .557 | .889 / .000 / .111 | .999 / .000 / .001 |
| 0.95 → 0.85 | .000 / .000 / 1.000 | .001 / .000 / .999 | .001 / .000 / .999 | .001 / .001 / .999 |
| 0.95 → 0.75 | .000 / .000 / 1.000 | .000 / .093 / .907 | .000 / .365 / .635 | .000 / .828 / .172 |
| 0.95 → 0.65 | .000 / .008 / .992 | .000 / .685 / .315 | .000 / .985 / .015 | .000 / 1.000 / .000 |
| 0.80 → 0.80 | .003 / .000 / .997 | .059 / .000 / .941 | .218 / .000 / .782 | .615 / .000 / .385 |

`bench/selfcheck.py` enumerates every success-count pair, classifies it with the gate, and sums independent binomial probability products. This avoids Monte Carlo sampling error; the probability weights still use floating-point arithmetic. It models rate-based decisions under its assumptions, not the incidence of harness errors or hard-invariant violations.

A twenty-percentage-point drop from 0.95 to 0.75 therefore BLOCKs only about 36.5% of experiments at N=200; about 63.5% remain inconclusive. Equal agents at 0.80 reach PASS only about 21.8% of the time. Conservatism reduces erroneous decisions but consumes trials and leaves many changes unresolved. Sources: `docs/STATISTICS.md`, the committed self-check JSON above.

The planner makes this cost visible before execution. Its approved scope is the existing CP gate, independent arms, K=1, one look, and N≤400; it reports all verdict probabilities and the smallest tested N meeting the requested target, or “target not reached.” It does not discover the true rates or retroactively register historical experiments.

Planner evidence: `metrics/plan-0.95-vs-0.75.md` and `.json` (schema `arci.plan.v1`); unsupported designs (N > 400, K != 1, more than one look, Newcombe) are refused with exit 3 and a message beginning "unsupported design", exercised by `tests/unit/cli/test_plan_cli.py`; 0.365 (`metrics/plan-0.95-vs-0.75.json`: 0.3647316956588909); <<PLANNER: smallest tested N meeting P(BLOCK)>=0.80 on 20,50,100,200,400>>.

Optional descriptive `pass^k` reports the all-success estimator `C(successes,k)/C(n,k)` for a declared population under IID assumptions, without changing decisions. Delivery status and exclusions: shipped as the opt-in `arci report RUN --pass-k 1,2,4` (Markdown only); `tests/unit/report/test_pass_k.py` covers "unavailable" for n < k, ERROR verdicts and manifests declaring more than one look, and `tests/unit/report/test_report_pass_k_cli.py` pins the default report bytes of all 19 committed stores with the flag absent.

## 4. Three worked examples

**Ollama retry: an archival prompt comparison.** The arms differ in whether the prompt permits retrying a failed tool call. A timeout targets `reserve`. The checkout contains the reports, but no committed raw Ollama manifests/trial stores were located; this example is archival report evidence and is outside the byte-exact decision inventory.

Every row below is supported by `docs/results/README.md` and the named report under `docs/results/`.

| Attempt | Baseline | Candidate | Recorded verdict | Interpretation / report |
|---|---:|---:|---|---|
| Bridge defect | 17/30 | 15/30 | INCONCLUSIVE | Unusable measurement: advertised tool parameters were missing; `ollama-run1-n30-bridge-bug.md` |
| Corrected exploratory run | 29/30 | 23/30 | INCONCLUSIVE | Insufficient evidence; `ollama-run2-n30.md` |
| Server failure | 172/400 | 143/400 | ERROR | Full scheduled denominators; outage and harness race invalidate inference; `ollama-run3-n400-invalid.md` |
| Clean confirmatory run | 376/400 | 308/400 | INCONCLUSIVE | Difference bounds [−0.2445, −0.0921]; `ollama-run4-n400.md` |

The clean run’s upper bound does not cross −0.10. Its observed seventeen-point drop therefore remains INCONCLUSIVE. The later Newcombe reanalysis is descriptive and cannot replace the prospectively chosen verdict. Earlier unusable attempts remain disclosed. Sources: `docs/results/README.md`, `docs/results/ollama-run4-n400.md`.

**Jev triage: a planted escalation regression.** The endpoint supplies live answers while the harness caps confidence; the regression removes the required escalation behavior. Every cell below comes from `docs/results/jev/README.md`; sealed stores are under `docs/results/jev/2026-10-03/`, with valid run names prefixed `jev-live-`.

| Run | Baseline | Candidate/control | Verdict | Interpretation |
|---|---:|---:|---|---|
| Import-failure attempt | 0/n | 0/n | Includes PASS and ERROR | Unusable measurement; retained under `attempt-1-invalid/` |
| `b-clean-1` | 1/1 | 1/1 | INCONCLUSIVE | Clean-pair sanity check |
| `b-low_confidence-50` | 50/50 | 0/50 | BLOCK | Planted regression |
| `a-low_confidence-50` | 50/50 | 50/50 | PASS | Unchanged-agent control |
| `c-low_confidence-50` | 50/50 | 50/50 | PASS | Repaired-agent control |
| `b-low_confidence-50-node` | 50/50 | 0/50 | BLOCK | Official SDK command-agent path |
| `b-low_confidence-200` | 200/200 | 0/200 | BLOCK | Predeclared larger design; reduced bundle retained |
| `b-clean-50` | 50/50 | 50/50 | PASS | Exploratory addition, not pre-registered |

The low-confidence outcomes are determined by the injected cap and agent policies; live answers do not make this a measurement of naturally occurring uncertainty. Import failures also illustrate that equally broken arms can satisfy relative non-inferiority when their failures are counted as agent failures. The clean-pair check must inspect actual trial outcomes. The separate intent-calibration audit in `docs/results/jev-calibration/README.md` provides related evidence on intent datasets, not permission calibration.

**Frontier-scout guardrail: policy behavior under injected decision faults.** A uses the shipped rule, B is a constructed fail-open variant, and C is static-only. Every cell below comes from `docs/results/guardrail/metrics.json` and its generated `README.md`; store names have prefix `guardrail-live-` under `docs/results/guardrail/2026-10-05/`.

| Run | A | B or C | Difference bounds | Verdict |
|---|---:|---:|---|---|
| `b-ask-clean-1` | 1/1 | 1/1 | [−0.9875, 0.9875] | INCONCLUSIVE |
| `b-ask-provider_down-50` | 50/50 | 38/50 | [−0.4016, −0.0348] | INCONCLUSIVE |
| `b-ask-low_confidence-50` | 50/50 | 50/50 | [−0.0839, 0.0839] | PASS |
| `c-ask-clean-50` | 50/50 | 50/50 | [−0.0839, 0.0839] | PASS |
| `b-ask-provider_down-200` | 200/200 | 130/200 | [−0.4304, −0.2537] | BLOCK |
| `b-all-provider_down-200` | 187/200 | 138/200 | [−0.3570, −0.1231] | BLOCK |

All six stores are retained. At N=50, the sample contained 12 dangerous commands, versus 65/182 in the `ask` population; the observed comparison was INCONCLUSIVE despite the preregistration’s expected BLOCK. The N=200 design was separately predeclared, not an outcome-dependent extension. On the whole-set sample, A’s 13 failures were dangerous commands already allowed by the static policy. Sources: `docs/results/guardrail/metrics.json`, `docs/results/guardrail/README.md`.

An `ask` can satisfy this oracle without completing useful work or authenticating human approval. The hook code ran through the harness boundary, outside a native coding-agent session. Outages were injected and bypassed the upstream provider. These results establish bounded hook behavior on the declared sample, not native enforcement or provider outage rates. Source: `docs/results/guardrail/README.md`.

## 5. Reproducibility

The committed tests cover byte-exact re-derivation of eighteen decision files: twelve Jev decisions, including five invalid-attempt decisions, and six guardrail decisions. They copy inputs into temporary directories, invoke the CLI in subprocesses, compare the complete generated bytes, and check the expected exit code. A BLOCK, INCONCLUSIVE, or ERROR exit can therefore be a successful reproduction. Sources: `tests/unit/stats/test_wilson_quantile_pin.py`, `tests/unit/examples/test_guardrail_results.py`. The interrupted invalid Jev store `docs/results/jev/2026-10-03/attempt-1-invalid/jev-live-b-low_confidence-200/` has no committed `decision.json` and is not counted as another reproduced decision.

Two portability defects were corrected before this package. A one-ulp platform difference in the inverse-normal value affected sealed Wilson display bounds; the 95% value is now pinned to `1.9599639845400536`. Separately, libm-dependent CP tail evaluation could change bisection results. Integer comparisons now evaluate tails exactly at the supplied binary64 inputs, retaining the existing sixty bisection steps. “Exact” describes the binomial construction and tail comparison; returned endpoints remain floating-point values. Sources: `src/arci/stats.py`, `CHANGELOG.md`.

The CP correction re-derived six Jev and five guardrail decisions from unchanged manifests and trials. Bounds and decision seals changed; verdicts, counts, exit codes, stopping histories, and rendered reports did not. The Wilson normalization also changed some display fields by one or two ulps. These historical normalizations are disclosed in `docs/results/jev/README.md`, `docs/results/guardrail/README.md`, and `CHANGELOG.md`; they are not permission to reseal archived bundles for this package.

`.github/workflows/ci.yml` defines Ubuntu checks and macOS statistics checks on Python 3.11 and 3.14. Workflow configuration is distinct from evidence that the final release head passed: <<REPRO: exact PR-head and post-merge CI URLs, commits, platforms, and outcomes>>.

The committed minimized bundles contain no embedded source files and seal different absolute interpreter paths: `/home/user/agent-reliability-ci/.venv/bin/python` for Jev and `/Users/ajay/Developer/.arci-worktrees/guardrail-live/.venv/bin/python` for the guardrail. Reproduction recreates those paths with the required source/environment; changing the bundle would change the evidence. Sources: each campaign’s `min-bundle.json`, `docs/reports/ci-gate-2026-10-06/reproduction/README.md`.

The preliminary log `docs/reports/ci-gate-2026-10-06/logs/docker-replay-probe-2026-10-05.txt` records REPRODUCED for both bundles with networking disabled. Final package evidence remains: <<REPRO: pinned source, container image digest, dependency inventory, and clean-clone check>>; `REPRODUCED: failure reproduced`, exit 0 (probe of 2026-10-05, `logs/docker-replay-probe-2026-10-05.txt`); `REPRODUCED: failure reproduced`, exit 0 (same probe); `examples/retry_agent/hero_demo.py --n 200` from the release source on 2026-10-05 (`logs/hero-demo-2026-10-05.txt`): A vs B BLOCK (exit 1), A vs A PASS (exit 0), the reduced bundle is `1-minimal` keeping only `tool_timeout`, offline replay `REPRODUCED`, and A vs C PASS under its own frozen experiment.

## 6. Related work and honest positioning

The following are documentation comparisons checked on 2026-10-05, not matched performance experiments.

[evalsig](https://github.com/vtensor/evalsig/blob/main/README.md) documents power planning, three-way gates, paired inference, clustered analysis, and sequential monitoring; arci’s narrower contribution is the experiment contract connected to fault diagnosis and replay. [Chronicle](https://github.com/theagentplane/chronicle) records decision boundaries and supports cut-point replay; arci requires exact consumption of its recorded boundary interactions. [agent-chaos](https://github.com/deepankarm/agent-chaos/blob/main/README.md) supplies tool and generative-model failure scenarios, overlapping arci’s resilience-testing purpose.

[AgentChaos, 2026-08-07](https://arxiv.org/abs/2608.06790), studies runtime faults at the LLM HTTP boundary, which arci’s present generative-model integration does not cover. [AGENTCHAOSBENCH, 2026-08-04](https://arxiv.org/abs/2608.14680), evaluates fault detection and localization across tool, model, guardrail, and inter-agent boundaries, providing direct related work for boundary-fault diagnosis. [HAL reliability](https://hal.cs.princeton.edu/reliability/) evaluates consistency, robustness, predictability, and safety across agent benchmarks; arci gates a prespecified task-condition comparison.

[Promptfoo](https://github.com/promptfoo/promptfoo) provides evaluation and regression-testing infrastructure, with repeated-success work linked from the demand signal above. [Inspect AI](https://inspect.aisi.org.uk/) supplies composable agent evaluations, tools, scorers, logs, and sandbox integrations. [Microsoft’s AI Agent Evaluation task](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluation-azure-devops) documents CI evaluation with confidence intervals and pairwise statistical comparisons.

[Braintrust](https://www.braintrust.dev/learn/ci-cd/v0) documents experiment comparisons and score-based CI gates. [LangSmith](https://docs.langchain.com/langsmith/evaluation) supports dataset-based evaluation and experiment analysis. [Langfuse](https://langfuse.com/docs/evaluation/experiments/compare-experiments) connects experiment comparisons to traces and repository-defined release policies. This report does not claim those systems lack statistical extensions or equivalent workflows.

Arci currently has no paired statistical estimator, although it can share scenario seeds; no anytime-valid inference, although it supports frozen finite looks; no multi-task aggregation; no general generative-LLM API fault boundary; and no cut-point replay. Sources: [statistical contract](../../STATISTICS.md), [boundary design](../../design/0002-out-of-process-boundary.md), [replay implementation](../../../src/arci/replay.py).

## 7. Limitations and what we do not claim

The binomial interpretation requires the declared sampling assumptions. Shared seeds do not make the planner’s independent-arm probabilities applicable to every paired campaign. Reused command variants cannot be pooled as independent evidence. `prior_runs` is supplied by the author; arci neither discovers omitted attempts nor enforces a cross-run error budget. Sources: `docs/STATISTICS.md`, `docs/results/guardrail/README.md`.

The oracle and environment remain trusted. Record hashes establish integrity relative to declared contents, not authorship. Replay reproduces recorded interactions under a compatible environment, not fresh model behavior. The worked examples do not establish broad production effectiveness, useful-work performance of abstaining guards, or native enforcement. Sources: `docs/TRUST_MODEL.md`, the campaign READMEs.

The approved package’s must-not-claim list is retained verbatim:

> Must not claim: first agent firewall / first statistical CI gate / first decision-boundary fault injection / first executable claim verification / novel statistical method; universal or permission calibration from intent datasets; exact Newcombe coverage; anytime-valid inference; native Claude enforcement from synthetic inputs; authenticated approval from unsigned receipts; production-safe autonomy; small-regression detection without power numbers; ACS certification, compliance, adoption, or superiority beyond the measured comparison.

## 8. How to verify this report

From the repository root in the release environment:

```bash
just check
just frozen
.venv/bin/pytest -p no:cacheprovider \
  tests/unit/stats/test_wilson_quantile_pin.py \
  tests/unit/examples/test_guardrail_results.py
.venv/bin/python docs/results/guardrail/summarize.py --check
```

The subprocess tests operate on copies. Running `arci gate` directly on an archived store rewrites its derived outputs.

After the reproduction tooling is committed:

```bash
.venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --check
# the two-stage recipe in `reproduction/README.md` (stage 1 installs the pinned source into the sealed Linux path with network on; stage 2 replays with `--platform linux/amd64 --network none`, the macOS worktree path recreated as a symlink)
```

Verify the downloaded Release assets using `shasum -a 256 -c SHA256SUMS` from the manifest’s documented working directory. Release verification: <<REPRO: Release URL, source commit, SHA256SUMS digest, asset inventory, working directory, and successful verification log>>. The evidence index must distinguish decision regeneration, agent replay, archival-only reports, and checks not completed.

## Appendix A. Frontier-scout verifier

| Defect | Before (`b9abe24`) | After the repair |
|---|---|---|
| D1 scope unenforced | out-of-scope additions and deletions passed | FAIL `SCOPE_OUTSIDE_ALLOWED` |
| D2 receipt treated as approval | local ask/allow/realized/self-declared approval passed | UNVERIFIED `APPROVAL_UNAUTHENTICATED` |
| D3 missing identity binding | unbound receipts or a hashless lock passed | FAIL (missing receipt hash or malformed lock) |
| D4 forged or malformed evidence | PR-authored approval passed; invalid JSON was skipped | forged approval stays UNVERIFIED; invalid JSON fails |
| D5 incomplete diff handling | rename escapes, quoted filenames, mode and binary changes, missing base passed | covered cases are non-pass; a failed diff stays UNVERIFIED |

The Action runs all four shell steps from `${{ runner.temp }}` and every Python invocation with `-I`, anchors repository, receipt and evidence paths, removes stale evidence, and fails when evidence is missing. The final inventory is 248 collected tests, including the 40-test verifier matrix (38 repository cases, one parser unit test and one documentation test), 15 Action tests (nine static checks and six isolation-module tests) and ten output/receipt hardening tests. The implementer reports all 248 passing; independent read-only rechecks passed, while fresh full-suite execution, real-runner execution and the default source-install branch were not verified in the re-review.. Insert the reviewed before/after results and exact commit for declared-scope enforcement, trusted-base policy/lock selection, malformed or unsupported evidence, forged approval, policy self-expansion, rename endpoints, unusual filenames, failed diff collection, and benign controls. Scope compliance and approval provenance must be reported separately. Unsigned local receipts remain supporting observations; approval remains UNVERIFIED without an authenticated source. Until the matrix is supplied, repair completeness and enforcing behavior are unknown.

Comparison frame, documentation checked 2026-10-05: [Notari](https://pypi.org/project/notari/) describes signed scope contracts and change verification; [MergeWarden](https://github.com/sjh9714/mergewarden) describes PR risk checks using base-commit policy and explicit incomplete-evidence handling; [AGENTOWNERS](https://github.com/streamentry/AGENTOWNERS) describes repository policy decisions tied to policy identity; and [Rulesync](https://github.com/dyoshikawa/rulesync) generates shared configurations for coding tools. These are distinct combinations of declared scope and evidence trust. Their behavior against this package’s defect matrix, deployment-specific trust roots, and comparative resistance to bypass remain unknown. The comparison covers README-level descriptions of Notari, MergeWarden, AGENTOWNERS and Rulesync at commit-pinned README revisions recorded in `docs/evaluation/verifier-2026-10-06.md` in frontier-scout (c6c472b, aba7262, 591e982, f14b5bd). No comparator was executed, so there are no comparative measurements; unknowns are marked unknown and no superiority is claimed..
