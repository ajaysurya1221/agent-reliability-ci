# Agent usability rehearsal: three cases, no human adoption claim

After the operator authorized autonomous agent follow-through, a fresh non-author
agent completed the three predeclared cases without requesting assistance.
Observation/classification took **143 seconds**; report filing/readback took
**258 seconds total**. These are timings for one automated reader, not estimates
of human onboarding time, adoption or retention.

Product revision tested: `417f1310cdf237712a8b9af134bfbb3a7e1f2f6f` (PR 15).
Execution used the previously verified local wheel in a fresh Python 3.13 venv,
outside the checkout, with `PYTHONPATH` cleared and `-P`. Temporary wheel SHA-256:
`2a10770dea974ec38981d6a941262041b035fac1ec48272f84cbda2b10cf4b5e`.
Its version metadata is 0.8.0 because the package version is frozen; it is the
unreleased implementation build, not the released v0.8.0 distribution.

## Outcomes

| Case | Observed behavior | Trace exit | Source gates | Strict composed CI exit |
|---|---|---:|---|---:|
| 1 | Candidate omits `decision:systemone`, records the static decision directly | DRIFT/1 | PASS/0 and PASS/0 | 1 |
| 2 | Candidate adds only `agent_result.result.diagnostic_label` to the compared content | DRIFT/1 | INCONCLUSIVE/2 and INCONCLUSIVE/2 | 2 |
| 3 | Selected baseline traces match across two archived experiment designs | MATCH/0 | INCONCLUSIVE/2 and BLOCK/1 | 1 |

The reader correctly avoided claiming a regression from drift or reliability
from matching. All selected trials were PASS, independently of their run-level
gates. The composed exits follow the existing recipe: preserve the candidate
source gate's nonzero exit first; otherwise use the diagnostic exit.

Case 1 is the archived guardrail's intentional static-only variant, not a newly
planted retry failure. Its observed call omission is not a reliability-regression
claim. Case 2 uses a new offline fixture with N=1 declared before execution; the
inconclusive result is retained. No design was extended or rerun to seek PASS.
Case 3 compares selected baseline-arm trials even though the second positional
source is named candidate in the diagnostic; its whole-run BLOCK is not a claim
that this selected baseline trial failed.

## Usability finding and bounded correction

The default path/hash output located differences but required targeted raw-record
inspection to name the omitted call and read the added label. The `<missing>`
label was an interpretation hazard: it names an absent value at the reported
pointer, while the containing event can still exist. The reader resolved this
before giving an incorrect conclusion.

The recipe now explains normalized-step lookup, the missing-value distinction,
sorted field traversal, terminal-field mapping and why raw values require targeted
inspection. This clarification followed the initial classification; it did not
assist that classification. The initial report and command ledger are retained
unchanged. No CLI output, format, statistical, replay or runtime semantics changed.

## Evidence and independent checks

- [Protocol](PROTOCOL.md), [case assignments](cases.json), [reader report](reader-report.md)
  and [all reader commands](reader-commands.txt) retain the task, observations,
  failed/truncated inspection attempt, limits and source identities.
- `results/case-*.json` are the integrator's CLI outputs, independently re-derived
  again after the reader task and matched byte for byte. All **29 source-file
  hashes** in `source-hashes-before.json` remained unchanged. The reader's own
  report supplies post-read hashes; the integrator supplies the before/after check.
- Case 2's tool events and all documented terminal fields were independently
  compared with canonical JSON bytes and were identical; only the preserved
  result label changed. This is a selected-record statement, not a statistical
  equivalence or causal claim.
- All **228 protected files** from the original implementation baseline remain
  byte-identical. Existing historical stores were read only. Production source,
  frozen contracts, dependencies and CI workflows are unchanged.
- Focused CLI/core tests pass; Ruff formatting/lint and strict types on the new
  fixture/verifier scripts pass. Final candidate and post-merge hosted checks are
  recorded in the follow-up PR receipt; prior feature CI is not substituted for
  a new candidate's acceptance.

Use a Python environment containing the unreleased trace-check implementation:

```bash
python plan/exec/trace-check/rehearsal-2026-11-03/verify.py
```

Expected output: DRIFT/1, DRIFT/1, MATCH/0, all three receipts match, and all 29
source-file hashes unchanged. This command reads existing stores only; it does
not contact their declared historical HTTP endpoint or execute their commands.

To create another offline metadata fixture, use a **new output directory**:

```bash
python plan/exec/trace-check/rehearsal-2026-11-03/build_fixture.py /tmp/arci-rehearsal-new
```

That second command executes only the packaged local fixture and independent
local oracle. It saves the experiment's exit 2 and full output. It refuses to
overwrite an existing directory. New raw records contain fresh timing fields;
do not replace the archived evidence or expect identical raw-file hashes.

## Limits

One automated reader, three selected cases, and one generated two-trial fixture
do not establish practitioner demand, human ease of use, adoption, reliability,
authentication, replay success or production performance. Blinding was limited:
the allowed recipe exposed generic missing-retry and MATCH/BLOCK examples. The
reader did not see the case-specific answer key or fixture implementation.

No live endpoint was contacted, no outreach occurred, and no versioned release
or frozen amendment was made. Human first-use and seven-day retention remain
**unmeasured**. No claim that the human pilot has been completed is made.
