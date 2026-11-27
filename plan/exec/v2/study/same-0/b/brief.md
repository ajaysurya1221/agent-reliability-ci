Do not open ~/.claude, ~/.codex, ~/.realornoise or ~/arci-data. Do not contact or stop the model server on port 11434. No network.

Independent count. Work only inside the current folder. Read nothing outside `input/`: no repository, no write-up, no other folder under /Users/Shared (another agent is doing the same count elsewhere; you must not look for it). Write your own code under `work/` with `python3 -I -B` and the standard library only (or `jq`). Do not import any `arci` package.

`input/REGISTRATION.md` is the registered text of what to count. Follow it exactly; where it is ambiguous, say so, choose the reading closest to its words and report the alternative count too.

`input/size0/RUN/trials.jsonl`: 14 self-comparison runs (`size0-d{1,2}-{q2,q4,q9}-{clean,null}`, `size0-d1-g12-{clean,null}`). Each line is one trial with `trial_id` (it starts with the round, for example `r000004:`), `pair_id`, `arm` (`baseline` or `candidate`), `task_id`, `outcome`.
`input/board0-clean/RUN/TASK/trials.jsonl`: ten clean runs, 16 task folders each, two trials per task.

Deliverables in the current folder: `counts.json` and `counts.md`.

1. Primary count (rounds 1 to 3 of each of the 14 runs): for every run the baseline passes and candidate passes out of 24, the difference, and whether it "shows a drop" (candidate 3 or more below), "shows a gain" (3 or more above) or neither. Then X and Y of 14.
2. Secondary counts: non-overlapping consecutive blocks of 1, 3 and 5 rounds starting at round 1, incomplete last block dropped. For each width: number of blocks; blocks where the candidate side has fewer passes, the same, more; blocks where the difference is ten points or more in each direction (1 of 8, 3 of 24, 4 of 40). Give every one of these also split by condition (clean, null) and by model (q2, q4, q9, g12). Check that each round has exactly 8 trials per side and report the block counts you found per run.
3. Board-0 clean rows: of the task-pairs (two trials of one task in one run), how many have two different outcomes, in total and per model slot (M1 to M5) and per day.
4. A plain list of every primary-count row and every three-round block: run, rounds, baseline passes, candidate passes.

Final message: X and Y, the secondary table, the Board-0 number, anything ambiguous, the files written. No long logs.
