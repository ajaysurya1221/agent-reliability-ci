# R1: read-only review of the records for `arci-logs/2`

You are the second reviewer, from another model family than the authors. **Read only.**
Edit nothing, run no git command that changes state, never open anything under
`~/.claude` or `~/.codex`, no network.

## Read

1. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/logs2/DESIGN-MEMO.md`, with
   its addenda after spike S0 (the choices; they are fixed).
2. The two drafts in the same directory: `0017-logs-2-draft.md` (design record 0017) and
   `STATISTICS_LOGS-2-draft.md` (the full revised statistics document).
3. In the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`: `docs/design/0016-logs.md`,
   `docs/STATISTICS_LOGS.md`, `docs/results/logs-selfcheck.md`, `src/arci/logs/*.py`,
   `tests/unit/docs/test_logs_docs.py`, `tests/unit/logs/test_report.py`,
   `bench/selfcheck_logs.py`.
4. `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/S0-logs2/REPORT.md`.

## Find

Report only real problems. For each: file, section, the quoted phrase, why it is a
problem, the corrected wording or the missing argument, and a severity (blocker, wrong,
unclear, minor).

1. **Statistics.** Is every claim proved by what precedes it? Check A1 to A4 as restated,
   the proof that the setting choice is fixed under permutation, Claim 1, Claim 2, the
   streak check's role, and each statement about the kept table. Look for a claim that is
   stronger than its proof, a condition used and not stated, and any way the choice of
   setting or the kept table can depend on the values tested.
2. **Numbers.** Every figure must be in `docs/results/logs-selfcheck.md`, in the S0
   report, or be marked as a placeholder for the 2.4.0 self-check. List any that is not.
3. **Consistency.** Between the two drafts; between each draft and the memo with its
   addenda; inside each draft. The record lists "Decisions of this record beyond the
   memo": check each against the rest of the record.
4. **Can it be built as written?** You will implement this. For each rule say whether the
   current code structure (`discover`, the two readers, `measures`, `decide`, `schema`,
   `report`, `html`, `cli`) can carry it, and name any rule that is ambiguous at the level
   an implementer needs: the order of steps when kept rows and log rows meet, what is
   validated in the record model, what the digest covers, how `arci-logs/1` records are
   still read, the all-or-none write with the kept table, the earliest-date rule.
5. **Can it be tested blind?** For the section "Acceptance, as tests can see it": name
   any item a test author could not turn into a test from the record alone, and any
   behaviour stated in the record that no item covers.
6. **Privacy.** Any path by which a string from a log, other than the three bounded
   exceptions (model id, effort, client version), could reach an output or the kept table.
7. **Wording.** Any sentence in a fixed text that claims more than the tool can know, or
   that a user could read as a claim of cause or of answer quality.

## Output

A numbered list of findings, most severe first, then one paragraph: are the records ready
to build from, yes or no, and what must change first. No long quotations of the drafts.
