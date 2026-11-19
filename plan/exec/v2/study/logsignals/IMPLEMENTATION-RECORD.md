# Log-signals study: implementation record (step 3 of the second registration)

19 November 2026. This is the record that step 3 of
[PREREGISTRATION-2.md](PREREGISTRATION-2.md) asks for. It is pushed before any pairing
happens. An earlier draft of a record, written under the first registration, was never
committed; the review of that draft is where the first registration's false limit was found.

- Registration commit: `f0ef8db5db19cfb9180a97f05427b1e451c58be8` (branch `v2/phase0`).
  SHA-256 of the registered text:
  `383738a6f14f6082c9d342dc5bca7d95c396f9a3e0cd0fbca4bda20665f04365`.
- Code commit: `efb181c4b386139a5fae266a3c93779730f98160` (branch `v2/logsignals`).
- SHA-256 of `bench/logsignals/analyze.py` at that commit:
  `37aa10908e8497d179a2b7e4ae06d9b0b873bceeefd6ecc43e103dbce67fb268`.
  This is the digest condition 1 compares with the result file. It is the same digest the
  registration prints for the earlier code commit: the file did not change.

**State when this record was written.** No program and no person has put a signal value beside
an outcome value of the same real session, in either half. Stage 1 and stage 2 have not run on
the real tables.

Programs have read real files, each on one side only. The registration's section "What was
looked at before writing this" and its "Files" table are the sources; this paragraph only sorts
them by period, adds no count and is not a second list. Before the first registration, among
them: the program that wrote the pool manifest, the two count programs, and the making of the
private month table that the round 3 simulation scripts read (section 5). Between the two
registrations: the signal extractor, the outcome extractor, the signal-side count program, a
short script that counted user ids per repository, the two audit count programs, and the
rebuild of the private month table. Since the second registration the orchestrating agent has
read the two private tables and the pool manifest only to compute their SHA-256 digests and to
count the lines of the two tables; no value was parsed. It also read the text of the private
program that wrote the manifest (reading 11).

This record describes code and counts. It states no result, no cause and no measure of quality.

**What rests on whom.** These items are reported by the orchestrating agent alone, which ran
the programs: the counts from private output, the order of events, the digests of private
files, that no other agent has opened a real file, and that no signal value has been set
beside an outcome value. The reviewing agents worked on the code, the texts and simulated
data. They did not see the private tables and cannot confirm those items.

## 1. The code and the tests

All files are at the code commit.

| File | SHA-256 |
|---|---|
| `bench/logsignals/__init__.py` | `f152b3dec89fc456987efa03f3cbfe79a39cdd674d81675c5557f08d7c457d3b` |
| `bench/logsignals/analyze.py` | `37aa10908e8497d179a2b7e4ae06d9b0b873bceeefd6ecc43e103dbce67fb268` |
| `bench/logsignals/check_result.py` | `17f277f5a1f6bf080c5232523725ae704a1c205b6395a468075b1651d9ccbd11` |
| `bench/logsignals/extract_outcome.py` | `ed6158ec92a69b6c6b819237cac58b8422fab064a30f99018c6ec65feb18f907` |
| `bench/logsignals/extract_signal.py` | `30b874c0bbda6091a6b54794c7bef69741c32de1297fe50a457c975612fa52cb` |
| `bench/logsignals/render.py` | `263a6b19a5e66b86fb4aba85d5f51a9e079f7758810f37b1f11935f76d99b2e1` |
| `bench/logsignals/signal_counts.py` | `94b284d8d141c9a37ab038695ca54788fcb8a58410f649464de6cf74022fa23f` |
| `bench/logsignals/INTERFACE.md` | `abebaec672ac3fbf5c0cc85074c186100f203025ce6bf70a7d0b4eba654f97a9` |

| File | SHA-256 |
|---|---|
| `tests/unit/logsignals/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tests/unit/logsignals/pipeline.py` | `1453af5e55b74b4415ff098d139841ad71f3c40d96cb35b00a942d3ea38ab108` |
| `tests/unit/logsignals/reachability.py` | `cb76ca9240b45dbfd4c2b2ec702a063873aaa242a87de099f04ffdbba23cdf67` |
| `tests/unit/logsignals/tables.py` | `53fe33112c83d60a0f9e2dd05b3282662a53969aa94ebe7638e0358597c7384d` |
| `tests/unit/logsignals/test_canary.py` | `49e502408b6f97b202ed17474136e7ba7a6be70c99ed74e17d47917554dc20c1` |
| `tests/unit/logsignals/test_check_result.py` | `6d0040b8b409c67295353f1bf7dff05b0e97e07a3394f261f31929ba3bc3d332` |
| `tests/unit/logsignals/test_extract_outcome.py` | `58eb132996c45216bb82eae5d6fc9addb8ccd6904c7b3b14fd372fefdf175a21` |
| `tests/unit/logsignals/test_extract_signal.py` | `fccda384454deef2da14751db221b2ae1938219f8d87dfc66785e002332c9503` |
| `tests/unit/logsignals/test_hostile_tables.py` | `a503c0d31a0cb93c0e3a7f0a91bb9ff062fabe8e8fe56237d0a47425ae180ea9` |
| `tests/unit/logsignals/test_module_boundaries.py` | `cad7ed0ab0d6bd2f3187dd5baf43ebf7c1d5bcef3324860b9966b34a281954f4` |
| `tests/unit/logsignals/test_page_rederivation.py` | `f371e52e0ae22335082d84d2340b5df6a706d065ea6a69fccc757f533fe72080` |
| `tests/unit/logsignals/test_refusals_and_determinism.py` | `f47ea38e672e7a6070b646a9cef1679afbad1711368dd904c22b38a8aed97330` |
| `tests/unit/logsignals/test_registered_checks.py` | `e47858a6c8f7e3ad79ad68c75ea4e160742953a5edff145e6d4fc9f69b3897f9` |
| `tests/unit/logsignals/test_render.py` | `fbd0241814aac48bf0569a0f8b774e8c00ba6942f6c1d8f2eba824152bc9374a` |
| `tests/unit/logsignals/test_signal_counts.py` | `e8ac4b8e583d8b3f99d117b5f9f7a0f6b8a6afe6283446e2690723b426f66ac3` |
| `tests/unit/logsignals/test_stage_separation.py` | `f0cdbc42ebe240beb61f959cabb53d5f62d627da5ba21b6f85c9a2c0c12ef21b` |
| `tests/unit/logsignals/test_statistics.py` | `e8423ba9b8e371775229ccf6a821e74b98783881c45f63a0873cdf85fdefc22b` |
| `tests/unit/logsignals/transcripts.py` | `bcb4f3001213b5c1512e8d93ea6c50c8924cbb0f22fc08b560be75594774a823` |

What each program does:

| Program | Reads | Writes |
|---|---|---|
| `extract_signal.py` | the pool manifest and the transcripts, through the unchanged reader | the private `signal.tsv`; counts only on screen |
| `extract_outcome.py` | two columns of the dataset's sessions table | the private `outcome.tsv`; counts only on screen |
| `signal_counts.py` | `signal.tsv` only | signal-side counts on screen; no file |
| `analyze.py --stage 1` | both tables; it never uses a session's signal value and its outcome value together | the check counts |
| `analyze.py --stage 2` | both tables | the result file; the only code that pairs |
| `check_result.py` | a result file | a verdict on its form and on the disclosure rules it can test |
| `render.py` | checks files, result files, a status file | the page |

### What changed after the second registration

Step 2 allows changes "only where this text differs from the first (the fixed sentences that
the page prints, and the comments and tests that quote them) or where the implementation record
names a fault". Three notes and seven file names in the table below are neither page sentences
nor quotations of one. They are read as comments that quote the registration: each stated a
sentence or a file name that the second text replaced, and no number any program computes
depends on them. The code commit differs from the commit the registration names
(`c65ed3cee64f75394d0100e2bdb971ed697580c3`) in these places and no others:

| File | What changed | Change of the registration |
|---|---|---|
| `render.py` | the note under the yardstick table | 12 |
| `render.py` | general limits 2, 3 and 9 | 13, 14, 15 |
| `render.py` | the facts of the first half (one clause added, one line added) | 16 |
| `render.py` | the facts of the second half (one line added) | 17 |
| `render.py` | condition 1 (two sentences added) | 27 |
| `render.py` | two comments that quote the note for a missed date | 21 |
| `tests/unit/logsignals/test_render.py` | the typed copies of the same sentences; one comment | 12 to 17, 21, 27 |
| `tests/unit/logsignals/test_page_rederivation.py` | one comment | 21 |
| `INTERFACE.md` | the description of the column `first_time` | 8 |
| `comparison/README.md` | the sentence on step 2 with the list of simulated sets; the second implementation's row ("the first registration"); a paragraph of history | 22 |
| `calibration/README.md` | how the private month table is rebuilt | 34 |
| seven files | the name of the registration file, `PREREGISTRATION-2.md` | 1 |
| `docs/results/log-signals-study-first-registration-ended.md` | new: the note of step 1 | step 1, not step 2 |

The seven files where the name of the registration file changed: `__init__.py`, `render.py`,
`INTERFACE.md`, `calibration/README.md`, `comparison/README.md`, `test_render.py` and
`test_registered_checks.py`. The new note of step 1 names it too. No program's control flow
changed, and no number any program computes changed. `render.py` prints the second text's
sentences where the two texts differ.

**The four programs whose digests the registration prints were left byte for byte as they
were**: `analyze.py`, `extract_signal.py`, `extract_outcome.py` and `signal_counts.py`. Two of
them wrote the private tables. (`check_result.py` did not change either.) Two of their
comments are therefore out of date, and they stay so on purpose:

- `analyze.py` says in its first lines that every definition comes from `PREREGISTRATION.md`.
  Read `PREREGISTRATION-2.md`. The definitions it implements are the same in both texts,
  with the two readings of changes 7 and 8 written into the second.
- `signal_counts.py` quotes a sentence of the first text about counts "not looked at before
  the text was written". The second text replaced it (change 20): those counts are now listed
  under "Between the two registrations".

`__init__.py` now says that `PREREGISTRATION-2.md` is the only source for every definition,
while `analyze.py` still points at the first text. The first statement is the true one.

Some comments in the code and the tests cite "Decision" numbers. Those are the numbers of the
build briefs written under the first registration, which are not committed. They are not the
numbers of section 6.

`INTERFACE.md` is the note on file formats that the second implementer worked from. Its row
for `first_time` said "time of the session's first main-thread response". It now says the
earliest timestamp among the session's main-thread responses, counted or not, which is what
`extract_signal.py` has written since before the comparison. The second implementation reads
the column and does not compute it, so the comparison does not depend on that row. SHA-256 of
`INTERFACE.md` as the second implementer had it (at commit `c65ed3c`):
`69c9011f78dc2930f44ddd79e9465d0fa13090d1b29902432be796ea0719476d`.

### Checks

Run by the orchestrating agent at the code commit, in the repository's environment:

- the study's tests: 265 passed, 1 skipped (the skipped one is the test of the published folder,
  which does not exist yet);
- the whole suite (`.venv/bin/pytest` with no path, from the repository root):
  5537 passed, 22 skipped. That is pytest's own summary line. 13 of the 22 are whole
  test files skipped because an optional package is not installed; 9 are single tests;
- `ruff format --check`, `ruff check`, `basedpyright` (strict), each on the whole repository:
  clean;
- `shasum -a 256 -c FROZEN.sha256`: 77 files, all the same. No file under `src/arci` changed.

The hostile-input and canary tests are among the study's tests. They passed before the
extractors opened any real file, and they pass at the code commit.

Two agents that did not write the change of section 1 reviewed it before it was committed.
One read every part of the difference against step 2's rule, compared each fixed text of the
page with the registration character for character, and changed words and phrases back to the
first text on a copy to see the tests fail; they did, five times out of five, and the smallest
change was a single word. The other built 15 kinds of page from simulated tables, searched each
for 21 sentences of the first text and found none, and checked the limits, the facts, the
yardstick note and the conditions on each. Both accepted the change. Both found one comment
that still quoted the first text; it was corrected before the commit. The first also left
notes on the out-of-date comments of the four unchanged programs, which this section states
above.

## 2. Step 2: the second implementation and the two requirements

**Every number in this section comes from simulated data.** None is a number of the study.

A separate agent wrote `comparison/blind_impl.py.txt` from the first registration and
`INTERFACE.md` alone, and wrote the simulated tables with `comparison/make_sets.py.txt`. It
listed 25 places where it had to choose a reading (`comparison/NOTES.md`). The data sets are
the planted set, the set with no link, and the edge cases as four data sets (`edge`,
`edge_few9`, `edge_ten`, `edge_eleven`). Each data set is two tables. A rerun of the script
writes the same bytes.

| File | SHA-256 |
|---|---|
| `bench/logsignals/comparison/COMPARE_FINAL.md` | `9e831037d98c60d845b0479ff5c46d9887b52b5519ecee3de7c4af6958244374` |
| `bench/logsignals/comparison/NOTES.md` | `cbb3961ad4682520491edfe27e857b3e97fe0002e375cd0917b5dce058185654` |
| `bench/logsignals/comparison/README.md` | `6b7b3be9989aa85dd9ad98d4b1542443e144ab7907540cb63251adfc2fee14dd` |
| `bench/logsignals/comparison/SETS.sha256` | `a8b43aa50abb4ffdb80c6637ebc298a0e1a13b80564824fb144303b1b7d686c4` |
| `bench/logsignals/comparison/blind_impl.py.txt` | `194edc0685b428694133315a9bc0b7d65790dcd0951045e3d63b301b87efa4e6` |
| `bench/logsignals/comparison/compare.py.txt` | `d0bd0a1c043cebae89d14f1fdfdbfad86ca2cfa13386ba60ff5ada1fb417318d` |
| `bench/logsignals/comparison/expected/edge_confirmation.json` | `f1c417fb9083ad74ddfd3676b0ebfc3f0337d722fa68ebac3abb206ca5e95594` |
| `bench/logsignals/comparison/expected/edge_discovery.json` | `21b6fe7ef8df26f75d1ecbaf6786b417d9da6b617118b9880ceee336e7d36574` |
| `bench/logsignals/comparison/expected/edge_eleven_confirmation.json` | `e948f6ac4cf1948c60c82265fff7bd01900bf4041e14f401245c23e23c5b0c63` |
| `bench/logsignals/comparison/expected/edge_eleven_discovery.json` | `cdf35c3c1824b64c6935e9807a8962506095ed019ef3b483b805d77598bf6885` |
| `bench/logsignals/comparison/expected/edge_few9_confirmation.json` | `d08704c764af9e252ca36401a8dac68cb672262d1b719b8fbcc217657a216e64` |
| `bench/logsignals/comparison/expected/edge_few9_discovery.json` | `2c7d9bcf5b036e67b44ebf2df3ebce6ecf542f86a8e4a6623be95012fc71b1c0` |
| `bench/logsignals/comparison/expected/edge_ten_confirmation.json` | `9ba9951bcee5ce2484ec72ebbb0c7219bb108eb9eb7ac7ed788dc2615e1402f8` |
| `bench/logsignals/comparison/expected/edge_ten_discovery.json` | `60dab288b7295e2bd37ae77b8a97cee2414f8b756810f93bda4741bb79bb99f4` |
| `bench/logsignals/comparison/expected/none_confirmation.json` | `f7efbd2bce25e1959d0ea4f45c15cdcdaf3cf4de3be15cfbadea15feb5d9c6cb` |
| `bench/logsignals/comparison/expected/none_discovery.json` | `697ca60373a2178854d2453b804bf045a8675637408c9534a50ac3962efd36fa` |
| `bench/logsignals/comparison/expected/planted_confirmation.json` | `49675b49dc14639156b23c37f92791b1ce3dd9bf6bf6e747bb33a5731a4fe812` |
| `bench/logsignals/comparison/expected/planted_discovery.json` | `48031177e8a5dc31cf5a7d9b12d4f816a3b0d72f3fe2a2996b0e16e952680f77` |
| `bench/logsignals/comparison/make_sets.py.txt` | `3c67e10da47b11547a7bfd8d41204bafb4a9c1cbc1ef598b93bc92445f77e39c` |

**Both requirements hold at the code commit** (`comparison/COMPARE_FINAL.md`):

1. 660 numbers compared over the six data sets and both halves; 0 differ by more than 1e-9.
2. Repository-blocked `rho_bar` of the first measure, planted set minus the set with none:
   0.451 in the simulated first half and 0.281 in the simulated second half. The planted link
   was positive and both planted numbers are positive.

**The comparison was run again after the change of section 1**, as step 2 requires: the same
sets, the same second implementation, the same comparison program. The orchestrating agent
ran it before the commit and again at the code commit; one reviewing agent ran it in its own
folder. Each run wrote `COMPARE_FINAL.md` with the same bytes as the committed file. That was
expected, since `analyze.py` did not change.

**The one correction of `analyze.py` that step 2 allows has not been used.** Neither
requirement failed at any point.

What a reader should know about this comparison:

- **The registered code refused the tables as the agent wrote them.** Their paths did not have
  the form the code accepts. The comparison ran on copies with renamed paths. The rule is the
  function `normalise` in `comparison/compare.py.txt`: sort every path of both tables as plain
  strings, and name the path at position `i` of that order `transcripts/s<i>.jsonl`, with `i`
  written as five digits. The function stops if the new names are not in the same order. A
  control in the same program runs the second implementation on the renamed copies and
  compares with its own expected output: 0 numbers moved. Both sets of digests are in
  `COMPARE_FINAL.md`.
- **The first comparison ran before any review.** It gave the same counts: 660 numbers, 0
  differences. Its report is kept privately (SHA-256
  `6d51017b1a4aa966fd4a39d5a9592b2006858813cd02a4c765ba31551d5ad3ba`).
- **`analyze.py` changed between the first and the final comparison**, in three rounds of
  review fixes, all under the first registration. None was a correction under step 2, because
  no requirement had failed. They changed what is refused and what is written, not the
  arithmetic. The agent of the second review wrote its own recomputation from the
  registration and compared it with the function that computes the numbers. The third and
  the fourth review ran that same recomputation again on the later code (958 numbers
  compared, 0 differ); they did not write further ones. The fourth review also compared the
  code with its earlier copy (about 1,800 numbers compared, 0 differ).
- **What the agreement covers.** The numbers on these six data sets. It does not test the two
  extractors, and it does not show the two implementations refuse the same inputs.
- **The second implementation is not run on the real tables.**

Two of the orchestrating agent's own instructions to the builder were reversed during the
build, because the registration says otherwise:

- It first let a session without the second measure stay in the first measure's numbers. The
  text says every eligible session has the second measure, so the extractor stops instead.
- It then made each stage refuse a table whose other half did not match its registered
  counts. Step 7 confines a second-half mismatch to the second half, so that refusal was
  removed (reading 9 in section 6).

## 3. The two private tables

Outside the repository.

| Table | Rows | SHA-256 |
|---|---|---|
| `signal.tsv` | 855 | `68f65e4efc6f6c37a8fbbc93a12917b6fc7ed394775892c9528136f409f9a2f6` |
| `outcome.tsv` | 4,594 | `0207c517088c4b83b67a8a89953ea01badfcfb269d528df9be1726a1677fd29d` |

The orchestrating agent recomputed both digests when this record was written, and they are
the ones the registration prints. Every checks file and every result file records these two
digests, so a reader can see which tables a file was made from.

The counts made from them so far are in the registration, under "Between the two
registrations". This record adds no count. In particular it does not print the figures the
registration says are computed and not published.

**Every registered signal-side check figure was reproduced for both halves** before the second
registration (`signal_counts.py`, exit 0): sessions, repositories, sessions with a first
measure of exactly 0, and the six month counts. The outcome-side figures (79, 228 and 116;
107, 184 and 141) have not been checked against `outcome.tsv`. That is stage 1's work.

## 4. Corrections to the registration text

None. This record corrects no word of the second registration.

## 5. The simulation files of the design rounds

Committed under `bench/logsignals/calibration/` at the code commit. Six files are byte for
byte the ones the registration lists. Five are copies with one kind of passage withheld, each
marked `[WITHHELD: ...]` in the file.

| File in the registration | SHA-256 in the registration (original) | Committed as | SHA-256 of the committed file | Withheld |
|---|---|---|---|---|
| Round 2 brief `SPEC_D.md` | `baf916b8c005b9ff327867f0b7b710c3bfb0ba96e82c42d73c5e1beb7b791d27` | `round2_brief_SPEC_D.md` | `67c4f50602979ab3077851d87a875cb1bc96382b0eb5244ad3a8e19819bd1943` | the list of 33 session counts |
| Round 2 script A | `3e0e563980f0e666e724b516d3fd54fd511cf35a71efde89cc53118c17340cb4` | `round2_script_A.py.txt` | `7aab2e2c4375e7ba11d7becc1f37ee0a31d1345defffa55aeef2aad405983e69` | the list of 33 session counts |
| Round 2 script B | `d320308f631c1049e5a734f2b3e1430580b087621aa108140647952a1d6eef51` | `round2_script_B.py.txt` | `6dffd8b4d9e44a9052f2654d4066fe224308c01fc4ef45abc5f36958c88d91f4` | the list of 33 session counts |
| Round 2 reviewer's script | `ae1031582567f23f21d454310c02c005afdac0663dad03b26345a743ea0189c9` | `round2_reviewer_script.py.txt` | `39c7fae4731f92e15ed72a5a262c16fd6fcb65fd00b0f124ca662c92e7aecc1f` | the list of 33 session counts |
| Round 2 review | `000dfdef15be7c3579160e5b71f211473d22abc361b781cc66a4533de2857241` | `round2_review.md` | `099b5f83a1b527fca8fb27b0d43342f414ee0c9e67d0bb70b26c9b19a022efc3` | one repository's session count |
| Round 3 brief `SPEC_E.md` | `bd1a8e30d3e887f4f08cf26d9aa3cd0391375106f73c044806490daeee8dafd3` | `round3_brief_SPEC_E.md` | `bd1a8e30d3e887f4f08cf26d9aa3cd0391375106f73c044806490daeee8dafd3` | none |
| Round 3 script A | `ad9c89b30348d5d50a7557488fb581f485708431993193d060e61d2f13743a3f` | `round3_script_A.py.txt` | `ad9c89b30348d5d50a7557488fb581f485708431993193d060e61d2f13743a3f` | none |
| Round 3 script B | `7d91a196a76d7cc20da79cdf4f84e4f22c7c561e2409a7808da1744ed1a1307a` | `round3_script_B.py.txt` | `7d91a196a76d7cc20da79cdf4f84e4f22c7c561e2409a7808da1744ed1a1307a` | none |
| Round 3 reviewer's script | `fef5968f34b74fc3d41ea4b42208433f9c65e3a6491765d6736f443bb9303fc9` | `round3_reviewer_script.py.txt` | `fef5968f34b74fc3d41ea4b42208433f9c65e3a6491765d6736f443bb9303fc9` | none |
| Round 3 reviewer's results | `efada83ca36ee73a285f7c22ff8bed6abf8bb4458f941445b288c869a41aa7ef` | `round3_reviewer_results.txt` | `efada83ca36ee73a285f7c22ff8bed6abf8bb4458f941445b288c869a41aa7ef` | none |
| Round 3 review | `03cc28e5cd927ce67a251cce2f79a9c7729f5947d42d71ab8270d08b3ed0f6cb` | `round3_review.md` | `03cc28e5cd927ce67a251cce2f79a9c7729f5947d42d71ab8270d08b3ed0f6cb` | none |
| (not in the registration) | | `README.md` | `966d15b468968b3a52c09e412d999d50875c9e34d8b9fe588ccdd6c197639eff` | |

- **The scripts are stored with a `.txt` suffix**, so the repository's linter and type checker
  skip them. Their bytes are otherwise the originals', apart from the withheld passages.
- **The three round 2 scripts do not run as committed.** The withheld list is their input.
- **The round 3 scripts need one private table** that is not committed: one row per repository
  of the first half, its session count and its count per month, April to September 2026.
  SHA-256 `3952cdfdaa23650787fd16cf5e27c9f4c465b70310d5f00a3a0ebebbe98a526b`. How to rebuild
  it from `signal.tsv`: keep the rows of the first half; for each repository key count its
  rows and its rows per month label; write a header line `n`, `2026-04` to `2026-09`, then one
  line per repository with those seven integers, tab separated, ordered by the seven integers
  from largest to smallest, each line ended by a newline. The orchestrating agent rebuilt it
  this way on 19 November 2026, between the two registrations, and got the same digest.
- **The originals stay private**, outside the repository.

## 6. How the code reads the registration where the text leaves room

These are not corrections. No words are replaced, and none of these readings changes an item
that cannot be corrected. Each is a choice the text left open; they are written here so that a
reader can check the code against them. The list comes from the build under the first text,
from one pass by a reviewing agent over the second text and the code, and from the review of
this record. Two reviewing agents, one on each of the first two drafts of this record, and
the consultant looked for a reading that changes a protected item and found none.

**Runs and files**

1. **The two runs of step 5.** Stage 2 takes exactly one of `--first-run` and
   `--second-run-of FILE`. The first run stamps the clock. The second run reads the start time
   from the first run's file, reads nothing else from it, and must write into another folder.
   The orchestrating agent runs each once. Nothing in the code stops a second `--first-run`;
   that would be a second start, and it will not be made.
2. **Where the files of steps 4 and 5 are committed.** On the records branch `v2/phase0`, under
   `plan/exec/v2/study/logsignals/run/`. Condition 1 says the chain is checked on that branch;
   the folder name is this record's choice.
3. **Who says "not an answer".** No program decides it alone. The orchestrating agent can name
   a failed condition for a half in a status file, and the page then prints that condition.
   When the status file names none, the page program adds condition 2 if the checks file says
   a count differs, and condition 3 if the repository blocks of the first measure miss the
   floor. A named condition takes the place of an automatic one, so when more than one
   condition fails the page names the one in the status file. The orchestrating agent will
   not name another condition for a half whose check counts differ. The page program refuses
   one case: a half whose check counts all match and that has no result file, outside the note
   for a missed date. So it cannot write a page for a failure found after stage 1 has matched
   and before stage 2 has run. Two things could fail that early. One is a privacy test: then
   the notice of reading 21 is published. The other is the first clause of condition 1, that
   the registration commit is an ancestor of this record's commit. It holds when this record
   is committed on `v2/phase0` on top of the registration commit, and the agent of step 6
   checks it. If it did fail, the page with "not an answer", the failed condition and the
   check counts would have to be written by hand, because this program would refuse.
4. **Condition 1 is checked by hand and by the separate agent of step 6.** No committed program
   checks the commit ancestry or the dates.
5. **What `check_result.py` can and cannot do.** It tests the form of a result file: the exact
   set of keys, the printed formats, the two floors as judged by the `m` and `W` the file
   itself gives, that the number without shared users stands alone, the form of the digests
   and commits, and the spelling of the start time. It compares the sessions and repositories
   with the checks file. It cannot recompute any `rho`, and it cannot see disclosure rules 1,
   2 and 5 in substance. The registration says the recount of step 6 is the only check on the
   result file itself.

**Tables the stages refuse**

6. **A format violation stops a stage and nothing is written.** Among them: a path of another
   form; an outcome value that is not written the way Python writes a float, or lies outside 0
   to 100; a signal row with no outcome row; a repeated path; a session length below 20; more
   zero counts than responses; a missing or malformed second measure; a malformed model name,
   month, user key or time; a wrong header row; bytes that are not UTF-8. Most of these forms
   are `INTERFACE.md`'s, not the registration's. `signal.tsv` is read whole, so a violation
   in a row of the other half also stops the stage. The outcome value is parsed only for the
   paths of the half being run.
7. **The path form.** `transcripts<digits>/<name>.jsonl`, where the digits may be absent.
8. **Stage 2 checks more than step 4 asks.** It recounts the check counts itself and refuses to
   run unless the committed checks file, its own recount and the registered figures agree.
9. **The other half.** Neither stage refuses a table because of the other half's counts. Step 7
   confines a second-half mismatch to the second half. The comparison of both halves on the
   signal side was made once, by `signal_counts.py`, before any pairing. The stages are tied to
   the tables by their digests.
10. **The number without shared users needs the other half's rows.** Stage 2 refuses a signal
    table that holds no row of the other half. Without those rows nothing would be excluded,
    and the number would silently equal `rho_bar`.

**What the tables hold**

11. **The half, the repository key, the month and the user key come from the pool manifest.**
    The signal extractor copies them and checks only their form. No committed program
    recomputes the registered rule for the halves. A private program wrote the manifest before
    the first registration. SHA-256 of that program, which the registration does not list:
    `0d5d850aed07ebbf2e75780a18e1e613f0c8b071e5b43cc7b86dc342cd698aa9`. The orchestrating agent
    read that program again for this record: it applies the registered rule, an even first hex
    digit to the half the files call `discovery` and an odd one to `confirmation`. The
    registration pins the manifest itself at SHA-256
    `53f3a0277d10d0b8dd177c5835619a9f08440110d0e6ab8aaa85fb3e62363638`, and the manifest on
    disk has that digest. The digest fixes the manifest's bytes; that the rule was applied
    rests on the reading of the program. The outcome count program of the first registration
    applied the same rule on its own. Its counts were made on the sessions the signal side had
    found eligible, as the registration says, so the two are not fully independent.
12. **What the signal extractor does with a session it cannot use.** A transcript on which the
    unchanged reader raises an error is counted as a reader failure and is not eligible. Three
    things stop the whole extraction, because an eligible session may not be dropped: an
    eligible session with fewer than 10 counts above 0 (section 2); a model name that would
    not be safe to write; and a fault while the extractor reads the reader's result, for
    instance a main-thread response without a time. So the empty `first_time` that the table
    format allows cannot come from this extractor. None of these happened: no reader failure,
    855 rows written.

**Numbers**

13. **A session without an outcome value.** The text says the outcome is used as the table
    gives it and that no session is deleted. If a session's outcome were empty, the code would
    keep it in the printed session and repository counts, cut the session-length thirds with
    it in place, and leave it out of every block's `n_b`. A path with no row at all in
    `outcome.tsv` stops the stage. **This case cannot change any number the study publishes.**
    The outcome extractor found a value for every pool session, and the registered outcome
    counts of each half add up to all its sessions (79 + 228 + 116 = 423; 107 + 184 + 141 =
    432). If a value were missing, stage 1's counts would differ from the registered figures
    and stage 2 would not run.
14. **"Constant" is judged exactly.** A block gives no `rho_b` when it has fewer than 2
    sessions, or when its signal or its outcome has fewer than 2 distinct values as held. The
    comparison is exact (rational numbers), before any floating-point value arises.
15. **The one square root.** The text says "exact rational arithmetic, with one square root in
    floating point at the end". The code forms the exact ratio of the squared numerator to the
    product of the two spreads, takes one square root, and gives the result the sign of the
    exact numerator. A block's number is exactly 0 only when that numerator is 0.
16. **The repositories that share an identified user.** The other half's user ids are those of
    its rows that carry one. A row without a user id matches nothing. A repository of the half
    being run is left out when any of its sessions carries one of those ids, whether or not
    that session has an outcome value. The number is then computed again over the repositories
    that remain; their own blocks do not change.
17. **A share is stored with its percent sign.** The registered format gives digits only. The
    result file holds the digits and a percent sign, from `0%` to `100%` (no value exists yet).
    The headline's `[S]%` is replaced by that whole string, so the page shows one percent sign,
    as the registered sentence does.
18. **When the repository blocks of the first measure miss the floor**, the sign count, the
    leave-one-out range and the number without shared users are numbers of that definition for
    that measure. Each is replaced by the same string, "not formed (k repositories, W units)".
    The page then prints no headline sentence, because the sentence has no first number to
    carry. It says "not an answer" with condition 3 and prints the numbers that were formed.
19. **The two "also printed" counts** stand beside the check table. They are not check rows and
    have no registered figure, so they cannot make a check read "different". Stage 2's own
    recount (reading 8) compares them too, and stage 2 refuses to run if the committed pair
    and its recount disagree.
20. **The leave-one-out sentence.** The headline gives two forms in one parenthesis. The page
    prints the one that applies.

**The page's own words**

21. **The title and the privacy notice.** The text fixes no title and says only that "a notice
    without any number is published". The page's title is "Log-signals study: result". The
    notice reads "A privacy check failed before publication. No number is published."
22. **Step 4's page.** Step 4 says the page "prints the check counts and no other number
    computed from the data". The page prints the found check counts beside the figures the
    registration fixes, the label and the sentence of the failed condition, and the two counts
    of reading 19. The registered figures, the label and the sentence are fixed text. The two
    counts are read as part of the check counts, because the registration lists them in its
    paragraph "Printed as checks".

**Private output**

23. **`signal_counts.py` writes no file.** It prints integers and fixed words on the screen of
    the orchestrating agent. Among them are the figures the registration says are computed and
    not published.

## 7. What else a reader should know

- **`extract_outcome.py` is tested in the repository against a stand-in** for the table
  reader, because the reader library is not installed there (the registration's item 3). It
  ran on the real sessions table in a separate environment that has the library. Stage 1 is
  the check on it: the outcome counts must equal the registered figures.
- **The private tables were written by code built under the first text.** The two extractors
  have not changed since (section 1). The registration says the same in "Order of work",
  step 2.
- **Two lines of the round 2 brief were assumptions, not counts.** The registration says so.
  No summary of session lengths is published, and none is printed on the page.
- **The round 2 review's "37% of the weight" is wrong.** The registration corrects it; the
  committed copy keeps the review's own words.
- **No agent other than the orchestrating agent has opened a real file.** The agents that
  reviewed this record and the code change worked on the texts, the code and simulated data.

## 8. What happens next

Steps 4 to 7 of the registration, unchanged, by 10 December 2026. Every command is run by the
orchestrating agent on the private tables; no other agent opens them. No code changes after
this record is pushed.

1. Stage 1 on the first half. Its checks file is committed.
2. Stage 2 on the first half, twice. If the two files differ, both are committed. If they are
   equal byte for byte, the result file is committed.
3. A separate agent recounts the published numbers from the result file, checks condition 1
   and checks the file against the disclosure rules. It reads the committed files only.
4. If every condition holds, the same code runs on the second half in the same way.
5. The page, the post and the README sentence, as the registration fixes them.
