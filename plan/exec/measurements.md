# Measurements log (orchestrator-recorded; receipts proper go to docs/measurement/receipts once T10 lands)

| when (UTC) | what | machine | result |
|---|---|---|---|
| 2026-10-13 03:36 | `examples/retry_agent/hero_demo.py --n 200` from the checkout, 8 workers | 15-core Apple Silicon Mac, Python 3.13.12 | 38.2 s wall, exit 0 |
| 2026-10-13 04:05 | T02 wheel smoke: `uv build --no-sources` from `sprint/demo` (2ae4bfd), then from an EMPTY directory `uvx --from <wheel> arci demo` (uvx env creation included) | same | 1:12.25 wall, exit 0, "All six steps held", A 192/200 B 132/200, 0 files left in cwd; wheel 115 KB (38 files, incl. arci/demo/* and arci/__main__.py); sdist 5.9 MB (unrestricted until T12) |

## Cold read of the README (AI-agent labelled; not a cold reader under protocol 1.4)

- When: 2026-10-13T07:08Z. Reader: Claude Opus 5.5 (effort high) general-purpose subagent with no
  project context, allowed to read only `README.md` at main `6f52431` (the first screen is the one
  that ships in v0.8.0; T12 changes only the pins below the fold). Scorer: Fable (orchestrator), key
  in `docs/measurement/ttfv-protocol.md` §5. Raw answers and per-question notes:
  `plan/exec/cold-read-2026-10-13.json`.
- Result: q1–q5 all correct (5/5); the BLOCK interpretation also correct. The reader read past the
  first screen (`read_whole_readme: true`; its own reading-time estimate 7 min). Memo target for
  cold readers: ≥ 80 % answer all five; this single AI-agent run is a check of the text, not a
  measurement of cold readers (none recruited in this run; HUMAN_INBOX 5).
