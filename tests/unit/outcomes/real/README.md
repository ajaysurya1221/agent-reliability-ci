# Real tool outputs used as importer fixtures

Produced on 2026-11-14 on macOS, offline (no model key, no account), by the tools themselves.
`scrub.py.txt` then replaced local paths and the host name with `/work`, `/npx` and `host`;
nothing else was changed. The generator inputs are kept beside the outputs with a `.txt`
suffix so that pytest, ruff and the type checker do not pick them up.

| Directory | Tool and version | How it was produced |
|---|---|---|
| `inspect/` | inspect-ai 0.3.289 (log `version: 2`), Python 3.14.6 | `python generate.py OUT`: 9 samples (one with an integer id), 3 epochs, scorers `match` and `includes`, a scripted solver, `mockllm/model`. The candidate raises in sample `task-03`, epoch 2 |
| `promptfoo/` | promptfoo 0.125.1 (results `version: 3`), Node 24.18.0 | `promptfoo eval -c ARM.yaml --repeat 3 --no-cache -o ARM.json -o ARM.junit.xml` with the scripted provider; `baseline-single.json` is the same without `--repeat` |
| `pytest/` | pytest 9.2.0, pytest-repeat 0.9.4 | `pytest --junitxml=single.xml`, and `pytest --count 3 --junitxml=repeat.xml` |

## What the files showed

Inspect AI
- A `.eval` file is a zip with `header.json` and one `samples/<id>_epoch_<n>.json` per sample.
  Its entries use Zstandard (zip method 93). Python's `zipfile` reads that from 3.14 on; on
  3.11 to 3.13 it raises `NotImplementedError`. The JSON form (`log_format="json"`, or
  `inspect log dump FILE.eval`) holds the same samples under a top-level `samples` list and
  reads on every supported Python.
- A sample has `id` (string or integer), `epoch` (from 1) and `scores`, a mapping from scorer
  name to an object with `value`. `match` and `includes` give `"C"` or `"I"`.
- A sample that raised has an `error` object and an empty `scores` mapping; the log's
  `status` is still `success`.
- The header lists `eval.dataset.sample_ids`, `eval.config.epochs` and `eval.scorers[].name`.

promptfoo
- With `--repeat`, `testIdx` numbers the rows (0 to 11 here), not the tests. The test is
  `repeatGroupId` (for example `test-0-vars-0`) with `promptIdx`, and the repetition is
  `repeatIndex` (from 0).
- Without `--repeat`, `repeatGroupId` and `repeatIndex` are null and `testIdx` is the test.
- `success` is the pass flag. `failureReason` is 0 for a pass, 1 for a failed assertion and
  2 for an error raised by the provider.
- Its JUnit output numbers the rows too (`test 3: word-alpha`), so it cannot be paired
  across repetitions.

pytest
- A test is `classname` plus `name`. `<failure>` is a failed assertion, `<error>` a failed
  set-up, `<skipped>` a skip. The root is `<testsuites>`.
- pytest-repeat ends the id with `[i-n]`, or `-i-n]` after other parameters
  (`test_word[beta-2-3]`).
