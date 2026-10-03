# Is Jev's confidence something you can gate on? A pre-registered audit of `jev-1.13.0`

One day (2026-10-03), one model version, two public intent benchmarks, 26,140 requests,
about USD 4.6 at list price. Pre-registered in
[`bench/jev_calibration/PROTOCOL.md`](../../../bench/jev_calibration/PROTOCOL.md), whose SHA-256
was posted on [PR #2](https://github.com/ajaysurya1221/agent-reliability-ci/pull/2) before the
first request. Every number below re-derives from the committed, hash-chained records in
`2026-10-03/records.compact.jsonl.gz` (see [Re-check](#re-check)); `2026-10-03/report.md` is the
analyzer's full output and `2026-10-03/metrics.json` the machine-readable version.

## The question

TypeSafe's Jev is a "System One" decision model: it answers typed questions (choice, score,
yes/no) with a probability for every option and a `confidence` number, and the vendor's routing
patterns say to act automatically above a confidence threshold and hand the rest to a person.
That only works if the confidence is honest. The launch post says it is ("calibrated: higher
confidence means higher accuracy") and that answers are consistent and fast; the vendor's own
evidence for classification is a 60-document cookbook. This audit asks the question an adopter
needs answered before gating on the number: **on real intent-routing data with label noise and
out-of-scope queries, is `jev-1.13.0`'s confidence calibrated, is it consistent, and what does
gating on it buy?**

Zero-shot throughout: the model sees the intent names with one-phrase descriptions (the name
with underscores removed), never a training example.

## Headline

| | CLINC150 (150 intents, 4,500 test + 1,000 out-of-scope) | Banking77 (77 intents, 3,080 test) |
|---|---|---|
| Top-1 accuracy, zero-shot | **0.921** [0.912, 0.928] | **0.801** [0.786, 0.815] |
| Supervised context row (TF-IDF + logistic regression trained on the full train split) | 0.925 [0.917, 0.932] | 0.914 [0.904, 0.924] |
| ECE of the top probability (15 bins) | **0.024** [0.020, 0.032] | **0.084** [0.073, 0.097] |
| Same, for the supervised row | 0.097 (under-confident) | 0.091 (under-confident) |
| Accuracy at `confidence >= 0.9` (coverage) | **0.970** [0.964, 0.975] (83%) | **0.930** [0.918, 0.941] (67%) |
| Accuracy of what that threshold hands to a person | 0.676 | 0.537 |
| Top-1 agreement, identical request repeated | 0.994 (in-scope); 0.9998 where p_max >= 0.6 | 0.986; 0.9993 where p_max >= 0.6 |
| Out-of-scope detection, AUROC | 0.977 (yes/no question), 0.974 (explicit option), 0.911 (1 - p_max) | no out-of-scope split |
| Latency from this container, p50 / p90 / p99 | 322 / 437 / 846 ms | 308 / 376 / 799 ms |
| Requests, failures | 16,500 + 400, 0 failed | 9,240, 1 failed (one HTTP 520) |

All seven pre-registered expectations were met (table in `2026-10-03/report.md`): H1 accuracy,
H2 calibration, H3 gating, H4 out-of-scope detection, H5 consistency, H6 speed, H7 the harder
benchmark.

## What was measured

Each item was sent three times in separate sweeps (identical requests), 12 concurrent requests
paced at 20 per second. CLINC150 requests bundled three questions evaluated in parallel by the
API: `intent_closed` (a Choice over the 150 intents), `intent_open` (the same plus an
`out_of_scope` option) and `is_oos` (a yes/no question that carries the intent list in its
instructions). Banking77 requests carried `intent_closed` only. A further 400 CLINC150 requests
(300 in-scope, 100 out-of-scope) carried the closed question alone, to check that bundling does
not change answers. Pass 1 is primary; passes 2 and 3 measure consistency. Exact questions:
[`questions.py`](../../../bench/jev_calibration/questions.py); estimators (exact binomial
intervals, ECE, tie-aware AUROC and average precision, bootstrap):
[`metrics.py`](../../../bench/jev_calibration/metrics.py), unit tested against hand-computed
cases and against `arci.stats`.

The supervised context row is not part of any hypothesis. It is a word-and-character TF-IDF
plus logistic regression fitted on the full `train` split (15,000 and 10,003 labelled examples)
with scikit-learn, evaluated on the same test items; the script is
`2026-10-03/baseline.py`.

## Results

**Accuracy.** On CLINC150 the zero-shot model matches the supervised row (0.921 against 0.925,
intervals overlapping) while never seeing a labelled example. On Banking77 it does not: 0.801
against 0.914. Banking77's 77 intents include near-duplicates that a name-only description
cannot separate, and the confusions say so: `order_physical_card` answered as
`get_physical_card` (26 of 40), `direct_debit_payment_not_recognised` as
`card_payment_not_recognised` (15), `beneficiary_not_allowed` as `failed_transfer` (14). On
CLINC150 the top confusions are the same kind: `reminder_update` as `reminder` (30),
`accept_reservations` as `restaurant_reservation` (26), `distance` as `time` (17). Richer
option descriptions, which the vendor's documentation recommends for confusable options, were
deliberately not used here so the result is attributable to the model rather than to prompt
work; they are the obvious next experiment.

**Calibration.** On CLINC150 the top probability is well calibrated overall (ECE 0.024). The
top bin holds 80% of the items: mean p_max 0.994, accuracy 0.973, so the model is over-confident
by about two points where it matters most, and roughly honest from 0.6 to 0.93 (bin accuracy
within a few points of bin confidence; the lowest bins are tiny). On Banking77 the picture is
different: ECE 0.084, with the 0.5 to 0.93 range over-stated by 15 to 20 points (for example
177 items at mean p_max 0.831 were right 64% of the time) while the top bin (62% of items,
mean 0.991) was right 94% of the time. The ranking is still informative (AUROC of p_max for
correctness 0.84 on both benchmarks). The supervised row is the mirror image: its ECE is worse
(0.09 to 0.10) because it is under-confident, which costs coverage rather than trust.
Reliability diagrams: `2026-10-03/reliability-clinc150.svg`, `2026-10-03/reliability-banking77.svg`.

**Gating.** The vendor's 0.9 cutoff on `confidence` keeps 83% of CLINC150 items at 97.0%
accuracy and sends the remaining 17% (67.6% accurate) to a person; on Banking77 it keeps 67% at
93.0% and sends 33% (53.7% accurate). The API's `confidence` and the raw top probability give the
same curves (for 150 options they are nearly the same number), so either can be thresholded.
Full coverage and threshold tables for both scores are in `report.md`.

**Out-of-scope queries.** Inferring "none of the above" from a spread-out closed answer is the
weakest route (AUROC 0.911, 39% false-positive rate at 95% recall). Asking directly is far
better: the explicit `out_of_scope` option reaches AUROC 0.974 and the yes/no question 0.977
(11% false-positive rate at 95% recall). Read literally, the open question recalls 87.0%
[84.8%, 89.0%] of the 1,000 out-of-scope queries at 81.9% precision while abstaining on 192 of
the 4,500 in-scope ones. Out-of-scope queries the closed question absorbs cluster in a few
intents: `fun_fact` (140), `definition` (79), `order` (72), `directions` (71).

**Consistency.** Identical requests repeated agree on the top-1 answer 99.4% of the time on
in-scope CLINC150 items (98.6% on Banking77), 99.98% where the first pass's top probability was
at least 0.6; the mean absolute change in top probability is 0.010, and the out-of-scope yes/no
value crosses 0.5 on 0.5% of items. All three passes agree on 97.3% of all CLINC150 items
(including out-of-scope) and 98.0% of Banking77 items. Bundling three questions into one
request changed the closed answer no more than resampling did (97.75% agreement with the
closed-only request on 400 items, identical in-scope accuracy of 0.91 on the 300 in-scope ones).

**Speed and cost.** p50 about 320 ms through this container's HTTPS proxy, which adds an
unknown constant; p99 between 450 and 850 ms by pass. 109.8 million input tokens for 26,140
requests, about USD 4.6 at the list price of USD 0.042 per million input tokens (a 150-option
request is about 5,600 tokens with three questions; output tokens are not charged). One
request in 25,740 bundled requests failed (HTTP 520, not retried because the runner retries
only 429 and 529); five needed a second attempt.

## What this means for a confidence-gated router

- On a task with distinct intents, gating at 0.9 is a sound default: 97% accuracy on 83% of
  traffic, and the hand-offs are the hard cases. On a task with near-duplicate intents, the
  same threshold keeps less traffic (67%) and the accuracy of what it keeps drops to 93%; the
  number to watch is accuracy *in the band you act on*, which `report.md` tabulates by
  threshold.
- Do not treat mid-range confidence as a probability on a Banking77-like task: 0.8 meant about
  0.64 there. Either calibrate on your own labelled sample or gate higher.
- For "none of the above", ask it. The explicit option or the yes/no question beats inference
  from the spread by a wide margin.
- Repeated calls are not a source of variance worth engineering around at these settings:
  answers above 0.6 moved on 2 items in 10,000.

## Limitations

- One model version, one day, one account, English, single-sentence utterances, two
  benchmarks; no adversarial inputs, long states or non-English text.
- Zero-shot with name-only descriptions. Richer descriptions, few-shot examples or a
  hierarchical first pass would likely move Banking77 and were not tried.
- The supervised row is one cheap model, included for scale, not as a state-of-the-art
  reference (fine-tuned encoders reach about 0.97 on CLINC150 and 0.93 on Banking77 in the
  dataset papers).
- No generative-LLM comparison: no such key was available in this environment. The vendor's
  cookbooks compare against LLMs on small samples.
- Probabilities come back rounded to two decimals, so log loss is clipped at 0.005 and the
  lowest reliability bins are coarse.
- Latency includes an HTTPS proxy hop of unknown cost; the vendor quotes 70 to 500 ms.
- Label noise in both benchmarks bounds the achievable accuracy and is discussed, not corrected.

## Re-check

```bash
export PYTHONPATH="$PWD"
.venv/bin/python -m bench.jev_calibration.analyze \
    --compact docs/results/jev-calibration/2026-10-03/records.compact.jsonl.gz --out /tmp/recheck
diff <(jq -S 'del(.chains)' /tmp/recheck/metrics.json) \
     <(jq -S 'del(.chains)' docs/results/jev-calibration/2026-10-03/metrics.json) && echo same
```

The analyzer verifies the compact store's hash chain and reports it under `chains`; every
other number in `metrics.json` is identical to the one derived from the raw stores (checked
before committing). The raw stores (143 MB of full probability vectors, also hash-chained; each
compact record carries its raw record's hash) are kept out of the repository and available on
request. To run the audit again: `bench/jev_calibration/run.py` with `TYPESAFE_API_KEY` set;
answers are sampled, so expect the consistency-level differences above.

## References

- Larson et al., 2019. An Evaluation Dataset for Intent Classification and Out-of-Scope
  Prediction (CLINC150). arXiv:1909.02027. Data: `clinc/oos-eval`, CC BY 3.0.
- Casanueva et al., 2020. Efficient Intent Detection with Dual Sentence Encoders (Banking77).
  arXiv:2003.04807. Data: `PolyAI-LDN/task-specific-datasets`, CC BY 4.0.
- TypeSafe, 2026-09-15, "Introducing System One Models & Jev"; docs pages Confidence, Models,
  Jev 1.13 jaggedness, Classification using confidence, read 2026-10-03.
