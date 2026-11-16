# Consult: the pre-registration of run 3, before it is committed and the run starts

You are the consultant. Work read-only: change no file, run no model, do not start Ollama,
do not run `arci run`. Never open anything under `~/.claude` or `~/.codex`, and do not
search any memory registry.

This is the point of no return for a one-shot registered experiment. Once the
pre-registration is pushed, the run starts and cannot be repeated under it.

Read, in `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/study/`:
`PREREGISTRATION-run-3.md` (the text to attack; its Prediction section still has a
placeholder, ignore that), `PLAN-run-3.md` (what the maintainer approved), `run-3.sh` (the
wrapper that will start the run), `order-desk-empty-message/agent.py` and `arci.yaml`,
`order-desk-empty-message-smoke/arci.yaml`, `run-3-smoke.log`, `counts-run-3/SPEC.md`, and
your own earlier advice `../reviews/R4-run3-design-astra.md`. The statistics contract is
`/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/STATISTICS_SUITE.md`.

Answer in under 500 words, verdict first:

1. GO, or GO after these changes (list each as an exact sentence to add, remove or
   replace), or NO-GO.
2. Any sentence in the pre-registration that claims more than the run can support, or that
   would let the result be reinterpreted afterwards.
3. Any way the wrapper can start the wrong thing, start twice, or leave a result that
   looks valid when it is not.
4. Are the four conditions for reading the verdict sound and complete? Is the 5% limit on
   time-outs and budget stops a reasonable fixed number, and is "no crash" too strict or
   too loose?
5. The maintainer was asked three times for a one-word prediction and has not answered.
   The text will then say that no prediction was made. Is that the honest way to record it?
