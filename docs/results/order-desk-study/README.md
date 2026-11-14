# Order-desk study: raw stores

Two committed, byte-for-byte copies of sealed `arci` suite stores (verified
with `sha256sum` before committing): `run-1/` (BLOCK at round 1) and `run-2/`
(INCONCLUSIVE after 5 rounds), each `manifest.json`, `trials.jsonl`,
`events.jsonl`, `decision.json`.

## Re-deriving a report from a clone

With the project installed (`uv sync` or `pip install -e .`):

```sh
arci report docs/results/order-desk-study/run-1/order-desk-gemma4-12b-vs-qwen3.5-4b@533c6d1a78ccc1a201eb7e265a61873244d48c2ac0e26cde5a50bc7dfd5f83bb
arci report docs/results/order-desk-study/run-2/order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@eaa438b195f418b66878a57422ab6229b2171c74dd8d6eb7ba097ec4a09b96fb
```

`arci report` re-derives the decision from the trials and recomputes every
seal: `VERDICT: BLOCK (exit 1); stored decision: match` for run 1,
`VERDICT: INCONCLUSIVE (exit 2); stored decision: match` for run 2.
`tests/unit/docs/test_order_desk_stores.py` does the same, in code, every run.

Hashes are integrity checks, not signatures: they show that each record matches
its hash and that the decision follows from these trials. They do not show who
ran the trials or on what hardware.
See [`docs/PROVENANCE.md`](../../PROVENANCE.md).
