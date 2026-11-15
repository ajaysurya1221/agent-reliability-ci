# First contact of the blind acceptance tests with the `arci-logs/2` build (2026-11-16)

221 cases written from record 0017 alone (132 functions). First run against commit
`3b446e1` on `v2/logs2`: **209 passed, 12 failed.** A referee agent ruled each failure
against the record. Nothing on disk was damaged in any case.

| # | Case | Ruling | Reason |
|---|---|---|---|
| 1 | streaky reason in Markdown | test | A Markdown block for a tool with a selected setting carries no reason text; only ERROR and `no_usable_setting` blocks do. |
| 2 | a day of file-edit results without a response | test | The fixture's own extra response falls on a day in the window and was not in the expectation. |
| 3 | canary run | test | A second session of the fixture carries an ordinary version, which matches the pattern and is rightly listed. No canary reached any output. |
| 4 | equal version tuples | **product** | The tie-break was reversed together with the numeric order; the record model's validator enforced the same wrong order. |
| 5 | JSON string shapes | test | Same fixture as case 3. |
| 6 | round trip with `--keep` | test | The first `--keep` run writes the table that the second run reads, so the two runs do not share inputs. |
| 7 | example label on the HTML page | **record** | The label is on the page, escaped; the record did not say how HTML output encodes text. |
| 8 | which row wins | test | The test compared its own label `stored` with the record's value `kept`; the write rule itself passed. |
| 9 | kept-day counts | test | A stored row makes its setting a candidate, so the fixture did not produce `no_usable_setting`. |
| 10 | unreadable table | test | The test read a file it had made unreadable, before the product ran. |
| 11 | a table path below a regular file | **product** | Classified as unreadable instead of absent, so a `--keep` run reported success without writing a table. Nothing was written, removed or replaced. |

Product fixes: commit `HEAD` of `v2/logs2` after this note (version order in
`measures.py` and `schema.py`; `kept.read`). Record 0017 gained two exact sentences
(ascending text order for equal tuples; HTML escaping). With the fixes: 211 of 221. The
ten test and record rulings go back to the blind author as rules, without any product
output. The referee also showed that with four versions of one numeric tuple the wrong
three were listed, and that a read-only run printed the could-not-be-read notice for a
table that never existed; both are covered by the two fixes.
