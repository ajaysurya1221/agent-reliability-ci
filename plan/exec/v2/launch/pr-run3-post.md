# Pull request for the run 3 post (the maintainer creates and merges it)

Branch `v2/run3-post` (`98a801b`), cut from `main` at `dd380d8`. Compare link:
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/run3-post?expand=1

Title: blog: the post about run 3 of the order-desk study

---

Adds the blog post about run 3 next to the first post, and a test that holds its numbers.

- `docs/blog/2026-11-order-desk-run-3.md`: the post. Same scope as the run 3 section of
  `docs/results/order-desk-study.md`: one 4B model in both arms, 8 stock-note tasks under
  the empty result, one message against the text `null`. It states the two errata and what
  the run does not show.
- `tests/unit/docs/test_order_desk_stores.py`: one new test. It rebuilds every count in the
  post's result section from the sealed run 3 store, the grid and the margin from the
  decision, and the run 2 figures the post quotes (34 of 52, 33 of 34, the other 16 tasks)
  from the run 2 trials. Ten wrong numbers were tried by hand; each fails the test.

Not held by a test: the smoke run's counts (6 of 8 and 3 of 8), which are in no committed
store. No change to code, to a pinned file or to the changelog (the two earlier posts added
no changelog entry either).

Checks on the branch: 5,156 tests passed, 21 skipped; lint, format and types clean; all 76
pinned hashes match.
