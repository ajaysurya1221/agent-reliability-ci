# Pull request for the README theme (the maintainer creates and merges it)

Branch `v2/readme-theme` (`4bd714f`), cut from `main` at `dd380d8`. Compare link:
https://github.com/ajaysurya1221/agent-reliability-ci/compare/main...v2/readme-theme?expand=1

Title: docs: every README figure and badge in one theme

---

## What

The README mixed two looks: the banner (neutral ground, blue and orange, system fonts) and
older figures (cream ground, serif titles, rust and green; two of them PNG and light only).
Every README figure and badge now uses the banner's theme.

- `docs/assets/src/make_figures.py`: one theme. Blue is the reference or the good outcome
  (A, PASS, REPRODUCED), orange the thing in question or the bad outcome (B, BLOCK, injected
  faults), a neutral bar is INCONCLUSIVE. System sans-serif and monospace type, no serif.
- `hero-*.svg`, `where-*.svg`: redrawn with the same words and numbers. The hero's evidence
  card gains one dot per trial (192 of 200 for A, 132 of 200 for B).
- `decision-*.svg`, `gate-*.svg`: new, generated, light and dark. They replace the two PNGs
  the README linked (`decision-boundary.png`, `calibration.png`). The gate bars are drawn to
  scale from the README table rows.
- `banner-*.svg`: unchanged byte for byte.
- `README.md`: the two PNG links become `<picture>` blocks; badges share one style and label
  colour. The CI badge keeps its own pass and fail colours, so a failing state stays visible.
- `tests/unit/docs/test_figures.py`: tests hold the palette, the two font stacks, equal text
  in light and dark, the colour of every verdict word, the hero's dot counts and grids, and
  the gate's bar widths on one scale.

## Two things a reader should know

- The old decision picture ended with "Jev was not run". The paragraph under it says it was
  run on 2026-10-03, so the new picture does not carry that line.
- The PNG files stay in `docs/images/`: the 2.4.0 README on PyPI links two of them on `main`.
- The where figure is taller than before (1600 x 716, was 1600 x 560), because no text is
  now smaller than 18px.

## How it was checked

- Built to a written brief, then two separate reviews (content against the old figures and
  the files the numbers come from; theme, layout by numbers, code and tests). Their findings
  are applied.
- All ten pictures were rendered in a browser at README width, light and dark, and looked at.
  Not looked at on Windows or Linux fonts.
- `python docs/assets/src/make_figures.py --check` passes; the docs tests pass (120).

## Pinned files touched

None.

- [x] This pull request does not change any file listed in `FROZEN.sha256`, or it links the
      design record that authorizes the change.

## Privacy

- [x] No session logs, log lines or log file paths are attached anywhere in this pull request.

No code change. No release is needed.
