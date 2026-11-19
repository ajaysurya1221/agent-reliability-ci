# The comparison of step 2

Step 2 of the registration (`plan/exec/v2/study/logsignals/PREREGISTRATION.md` on branch
`v2/phase0`) asks for a second implementation written from the registration alone, three
simulated data sets, and two requirements. These are the files of that comparison. Everything
here is made-up data: nothing is counted from a real file.

| File | What it is |
|---|---|
| `blind_impl.py.txt` | the second implementation, by an agent that saw the registration and `../INTERFACE.md` only |
| `make_sets.py.txt` | writes the simulated sets (fixed seeds; a rerun writes the same bytes) |
| `SETS.sha256` | the digests of the twelve tables `make_sets.py.txt` writes |
| `expected/` | the second implementation's output on those tables |
| `NOTES.md` | every place where the second implementer had to choose a reading |
| `compare.py.txt` | compares `../analyze.py` with `expected/` and writes `COMPARE_FINAL.md` |
| `COMPARE_FINAL.md` | the comparison on the committed `../analyze.py`, with the digest of every file read |

The scripts carry a `.txt` suffix so the repository's linter and type checker, which cover
`bench/`, skip them. To rerun, from the repository root:

```
mkdir -p /tmp/cmp && cp bench/logsignals/comparison/blind_impl.py.txt /tmp/cmp/blind_impl.py
cp bench/logsignals/comparison/make_sets.py.txt /tmp/cmp/make_sets.py
cp bench/logsignals/comparison/compare.py.txt /tmp/cmp/compare.py
cp -R bench/logsignals/comparison/expected /tmp/cmp/expected
.venv/bin/python -I /tmp/cmp/make_sets.py /tmp/cmp
.venv/bin/python -I /tmp/cmp/compare.py . /tmp/cmp /tmp/cmp/COMPARE_FINAL.md
```

The comparison shows that two implementations give the same numbers on these tables. It does
not test the extractors, and it says nothing about any real session.
