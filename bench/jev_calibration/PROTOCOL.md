# Pre-registration: a calibration audit of `jev-1.13.0` on intent classification

Written and committed on 2026-10-03 before any audit request was sent, except for the three
smoke requests disclosed below. Nothing in this file changes after the run; deviations are
recorded in the results write-up, never here.

## Why

TypeSafe's launch post for Jev claims the model is *calibrated* ("higher confidence means higher
accuracy"), *consistent* ("returns similar answers for similar inputs") and fast ("70 ms to
500 ms end to end"), and the documentation builds its routing patterns on gating by the answer's
`confidence`. The vendor's own evidence for calibration on classification is a 60-document
cookbook. The day-one runs in `docs/results/jev/` exercised the harness, not the model: every
clean decision came back at confidence 1.0. This audit measures the three claims on two public
intent-classification benchmarks that have real label noise and, in one case, out-of-scope
queries, at a sample size where the intervals are narrow.

The audit is zero-shot: the model sees the intent names and one-phrase descriptions, never a
training example. The numbers it produces are therefore not comparable to fine-tuned
classifiers, and this file says so before the numbers exist.

## Datasets

| Dataset | Split used | Items | Labels | Source (verified by SHA-256 before every run) |
|---|---|---:|---:|---|
| CLINC150 (Larson et al., 2019, "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction") | `test` | 4,500 | 150 intents in 10 domains | `https://raw.githubusercontent.com/clinc/oos-eval/master/data/data_full.json`, sha256 `36923c3705a59e08fe9c3883d8bc2dd966ef93e22cb78ac41171782a698d56e0` |
| CLINC150 out-of-scope | `oos_test` | 1,000 | `oos` | same file |
| CLINC150 domain map | | | 10 domains × 15 intents | `https://raw.githubusercontent.com/clinc/oos-eval/master/data/domains.json`, sha256 recorded in `data.py` |
| Banking77 (Casanueva et al., 2020, "Efficient Intent Detection with Dual Sentence Encoders") | `test` | 3,080 | 77 intents | `https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/master/banking_data/test.csv`, sha256 `d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d`; categories `.../categories.json`, sha256 `53261da888122daf2d120d925458631d9619e15d82e56052e7a42e535ce32b63` |

Both are CC BY licensed. The repository commits per-item results keyed by item id and does not
redistribute the texts; `data.py` downloads and verifies them.

The `train` and `val` splits are not sent to the model. They are used only for the classical
supervised context row (below), which is not part of any hypothesis.

## What is sent

One request per item per pass, model pinned to `jev-1.13.0`, `state` = the utterance as a plain
string, questions exactly as built by `questions.py` (the strings there are the protocol; this
section describes them):

- **CLINC150, bundled request** with three questions evaluated in parallel by the API:
  - `intent_closed`: a `choice` over the 150 intents. Option key = intent name; description =
    the name with underscores replaced by spaces. Instructions: "Which one of the listed intents
    does this request express?"
  - `intent_open`: the same 150 options plus `out_of_scope` described as "the request is not
    about any of the other listed intents". Instructions: the closed instruction plus "Pick
    out_of_scope if none of the listed intents fits."
  - `is_oos`: a `noul` whose structured instructions carry the list of 150 intent names and the
    question "Is this request about none of the `intents`? Answer yes only if no listed intent
    fits." Criteria: true = "no listed intent fits the request", false = "at least one listed
    intent fits the request".
- **Banking77, one question**: `intent_closed`, a `choice` over the 77 intents, built the same
  way. Banking77 has no out-of-scope labels, so no open or noul question.
- **Independence check**: for the first 300 CLINC150 test items and the first 100 `oos_test`
  items (in file order), one extra request carrying only `intent_closed`, to measure whether
  bundling questions changes the closed answer.

Three passes of identical requests per item (passes 1, 2, 3), sent in separate sweeps. Nothing is
added to the state between passes; the three smoke requests showed that identical requests are
already re-sampled (the noul moved from 0.37 to 0.35 on a repeat).

Pacing: at most 12 concurrent requests and a client-side cap of 20 requests per second, under
the documented limits (40 requests per second, 100K tokens per second). A 429 or 529 is retried
with exponential backoff up to 6 attempts, honouring `retry-after`; an item that still fails is
recorded with its status and excluded from accuracy denominators but counted in the invalidity
rule below. Every record is hash-chained (`prev_sha256`, `record_sha256`) and carries the
vendor's request id, client-measured latency, reported model and token usage. The key is read
from `TYPESAFE_API_KEY` and never written anywhere.

Expected volume: (5,500 + 3,080) × 3 + 400 = 26,140 requests, about 4,800 input tokens per
CLINC150 request (measured in the smoke test) and about 2,500 per Banking77 request, roughly
USD 4 at the list price of USD 0.042 per million input tokens.

## Smoke test, disclosed

Three requests were sent on 2026-10-03 before this file was written, to check that a 150-option
Choice is accepted and to see the response shape: "how would you say fly in italian" (twice) and
"how much has the dow changed today". Findings that shaped the protocol: probabilities are
returned to two decimals (so log loss is clipped, below); a noul that refers to "the listed
intents" without carrying the list is answered near 0.35 for both an in-scope and an
out-of-scope request, so the noul now carries the list in its structured instructions; the
open question put 1.0 on `out_of_scope` for the Dow query while the closed question spread
0.58 on `exchange_rate`. Those three items stay in the audit; their smoke answers are not used.

## Measures

Computed by `analyze.py` from the raw records; `metrics.py` holds the estimators and is unit
tested. Unless stated, "in-scope" means the 4,500 CLINC150 `test` items or the 3,080 Banking77
items, and the primary pass is pass 1; passes 2 and 3 serve the consistency measures and a
pooled sensitivity check.

- **Accuracy**: top-1 `choice` equals the label, with a two-sided 95% Clopper-Pearson interval.
  On CLINC150, reported for `intent_closed` and for `intent_open` restricted to in-scope items.
- **Calibration of `p_max`** (the probability of the chosen option): expected calibration error
  (ECE) with 15 equal-width bins, maximum calibration error, Brier score of `p_max` against
  correctness, and the reliability table (bin, count, mean confidence, accuracy). The same for
  the API's `confidence` field, which for a Choice with n options is `(p_max - 1/n)/(1 - 1/n)`.
  95% intervals for ECE by 1,000-resample bootstrap over items.
- **Log loss** of the probability assigned to the true label, with probabilities clipped at 0.005
  because the API returns two decimals.
- **Discrimination of correctness**: AUROC of `p_max` (and of `confidence`) for predicting that
  the top-1 answer is correct.
- **Selective accuracy**: accuracy on the covered subset when the least confident items are
  abstained to reach coverage 100%, 95%, 90%, 80% and 70%, and at the four thresholds the
  vendor's documentation uses (0.5, 0.6, 0.85, 0.9), on both `confidence` and `p_max`, with
  coverage and the accuracy of the abstained remainder.
- **Out-of-scope detection** (CLINC150, 4,500 in-scope versus 1,000 out-of-scope): AUROC, average
  precision (out-of-scope positive) and the false-positive rate at 95% out-of-scope recall, for
  three scores: `1 - p_max` of `intent_closed`, the `out_of_scope` probability of `intent_open`,
  and the `is_oos` noul. Plus the CLINC paper's operating point: in-scope accuracy together with
  out-of-scope recall when `intent_open` is read literally (choice == `out_of_scope`).
- **Consistency across passes**: top-1 agreement between pass 1 and pass 2, pass 1 and pass 3,
  and all three; mean absolute change in `p_max`; agreement restricted to items with
  `p_max >= 0.6` on pass 1 (the vendor's cookbook operating point); the same for the noul
  (mean absolute change, share of items crossing 0.5).
- **Bundling independence**: top-1 agreement and mean absolute `p_max` difference between the
  bundled `intent_closed` and the closed-only request on the 400 check items.
- **Latency**: client-side p50, p90, p99 per dataset, measured from this cloud container
  through its HTTPS proxy, which adds an unknown constant.
- **Descriptive**: per-domain accuracy (CLINC150), the ten most frequent confusions, and the
  intents the out-of-scope items are most often absorbed into.
- **Context row, not a hypothesis**: a TF-IDF plus logistic-regression classifier trained on each
  dataset's full `train` split and evaluated on the same test items, with its accuracy and ECE,
  so a reader can place the zero-shot numbers against a cheap supervised model trained on
  15,000 (CLINC150) and 10,003 (Banking77) labelled examples.

## Pre-registered expectations

Each is a prediction with a decision rule, written before the data. The write-up reports each as
met or not met with the estimate and interval; none is softened afterwards.

| # | Claim under test | Measure | Expectation |
|---|---|---|---|
| H1 | zero-shot accuracy | CLINC150 `intent_closed` top-1 accuracy, pass 1 | lower 95% bound ≥ 0.85 |
| H2 | calibration | CLINC150 in-scope ECE of `p_max`, pass 1 | upper 95% bootstrap bound ≤ 0.05 |
| H3 | gating is useful | CLINC150 accuracy on items with `confidence ≥ 0.9`, pass 1 | lower 95% bound ≥ 0.95, with coverage ≥ 0.5 |
| H4 | out-of-scope detection | AUROC of `intent_open`'s `out_of_scope` probability | ≥ 0.90 |
| H5 | consistency | CLINC150 in-scope top-1 agreement, pass 1 versus pass 2 | ≥ 0.95 |
| H6 | speed | CLINC150 p50 latency from this container | ≤ 500 ms |
| H7 | the harder benchmark | Banking77 top-1 accuracy, pass 1 | lower 95% bound ≥ 0.70 |

H1 and H7 are expectations for a zero-shot model given published fine-tuned results of about
0.97 (CLINC150) and about 0.93 (Banking77); they are not claims the vendor made.

## Validity

The run is valid if every pass completes with at most 0.5% of requests failing after retries,
every response reports `jev-1.13.0`, and the hash chain verifies. Otherwise the run is reported
as invalid, kept, and re-run after the cause is fixed; both runs stay in the results.

Items are never dropped for being hard, mislabelled or ambiguous. Label noise in both datasets is
known and bounds the achievable accuracy; it is discussed, not corrected.

## What this audit cannot say

One model version, one day, one account, English only, short single-sentence utterances, two
benchmarks. No comparison to a generative LLM's verbalised confidence (no such key is available
in this environment); the vendor's cookbooks make that comparison on small samples. No claim
about adversarial inputs, long states or non-English text.
