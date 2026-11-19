"""The log-signals study: the build of the registered description.

`PREREGISTRATION.md` (committed under `plan/exec/v2/study/logsignals/`) is the only source for
every definition, number, sentence and rule used here. These modules hold no definition of their
own.

- `extract_signal.py` reads transcripts through the unchanged Codex reader and writes the private
  signal table. It knows no outcome.
- `extract_outcome.py` reads two columns of the sessions table and writes the private outcome
  table. It knows no signal.
- `analyze.py` is the only code that ever puts a signal value beside an outcome value, and only
  in its stage 2.
- `signal_counts.py` prints the signal-side counts of both halves from the signal table alone.
  It reads no outcome and forms no pair.
- `check_result.py` checks a result file against the registered disclosure rules and formats.
- `render.py` writes the result page from a result file.
"""
