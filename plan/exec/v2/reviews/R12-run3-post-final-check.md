# R12: last check of the rewritten run 3 post (one agent, read-only, 17 Nov 2026)

Checked `launch/post-run-3.md` sentence by sentence against `study/RESULT-run-3.md`,
`study/PREREGISTRATION-run-3.md`, the first post, both reply drafts, run 2's store, and the
study folder's `tasks.jsonl`, `check.py` and `agent.py`.

No finding on: the allowed claim and counts (every number is a count; the only percentage
is the registered margin); forbidden claims; style (no dashes, no exclamation marks, no
sales wording). Answer: safe to show the maintainer as a draft.

Seven wording findings, all applied:

1. "In every trial the harness makes the first order lookup come back empty": the fault
   fired in 16 of 16 and 15 of 16 trials (one trial made no tool call). Now "is set to make".
2. "the other study files did not change": the result file says this of the study folder
   only. Now "the files of the study folder itself".
3. "registered fingerprint" was undefined. Now "the version of the script that ran is the
   version the registration recorded".
4. "three statistical verdicts": INCONCLUSIVE is not one. Now "three verdicts".
5. "So I put ...": the reason was two sentences back. Now "Because no verdict says
   \"better\", I put ...".
6. One sentence gave the margin without "of mean pass rate". Added.
7. "it is still open" next to the scripted test read as a contradiction. Now "I have not
   tested it with a model".

Length after the fixes: 1,028 words from the first paragraph to the line before "Check it
yourself" (the first post has about 800).
