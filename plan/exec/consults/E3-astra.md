````markdown
# Did this change make your agent less reliable?

ARCI (agent-reliability-ci) compares baseline and candidate agent versions repeatedly under the same predeclared test scenarios using an independent success check, returns `PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR`, and can replay a recorded failure.

```bash
uvx --from agent-reliability-ci arci demo
```

Replace these example references with your project's importable Python functions:

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
```

`baseline + candidate → same predeclared tasks/faults → repeated trials → verdict → minimise/replay`

**PASS means only this:** for this predeclared experiment, the evidence supports that any reliability drop from baseline to candidate is smaller than the allowed drop. It is **not** a claim of absolute reliability.

A small first run will often be **INCONCLUSIVE**. That is a valid result; use `arci plan` before choosing a larger confirmatory run.

ARCI observes calls that cross its tool boundary. It is not a sandbox, it does not replay model inference, and trace divergence shows where runs differ—not why.
````

**1. First-screen decision — 171 words**, including commands, verified using `plan/exec/scripts/first_screen_words.py`.

Deviations from the memo:

- Make the question the H1 and expand ARCI in the opening sentence so the question leads while the package remains identifiable.
- Use “test scenarios” and introduce the “independent success check” to apply the jargon table and explain who grades success.
- Add the reference-replacement instruction because the second command requires existing project functions.
- Replace “frozen” with “predeclared” in the pipeline to explain the timing requirement plainly.
- Replace “not shown to be worse” with affirmative supporting evidence because absence of evidence of regression can also yield INCONCLUSIVE.

Both commands, the small-run guidance and the boundary wording remain verbatim.

**2. Below-the-fold placement**

Under **Recorded result and evidence**, place the recorded **192/200 versus 132/200, BLOCK (exit 1)** result and both existing links, followed by the evidence links and complete “Re-derived means…” explanation, then the hero figure with unchanged alt text and artwork.

Move all badges, the security-policy link and the availability line into **Availability and project status**. Replace the old main/v0.7.0/no-PyPI wording only when release evidence supports the replacement.

Preserve the **Independence paragraph verbatim**, including its links, in its current position after Related work.

Exact section order:

```markdown
## Try the offline demo
### Recorded result and evidence
## Verdicts and exit codes
## How it works
## Where it has been run
## The gate, measured against itself
## Gate your own agent
### Advanced: Python manifest builder
### GitHub Actions
## What it does not do
## Roadmap
## Development
### Availability and project status
```

Begin **Gate your own agent** with the descriptor workflow; retain the Python builder under the advanced subsection. Move the clone-based demo instructions into Development.

**3. Absolute URLs**

Keep `<picture>`; set:

- `<source srcset>`: `https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/main/docs/assets/hero-dark.svg`
- `<img src>`: `https://raw.githubusercontent.com/ajaysurya1221/agent-reliability-ci/main/docs/assets/hero-light.svg`

PyPI therefore retains the light-image fallback when it strips `<source>`.

The proposed first screen contains no hyperlinks. Nevertheless, make **every relocated link from current lines 1–35 absolute**: recorded results/log, evidence report, frozen contracts, design records, workflow, reproduction recipe, citation file, badge images/targets, license, package metadata and security policy.

Use `https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/` plus the existing path for files, and `https://github.com/ajaysurya1221/agent-reliability-ci/tree/main/docs/design/` for design records. Retain existing absolute workflow/release destinations, updating the release target only after verification.

**4. Demo paragraph**

> `arci demo` runs a packaged copy of the seeded retry fixture, with no repository clone or model calls. At 200 trials per version, it computes **192/200** baseline successes and **132/200** retry-removed candidate successes fresh, yielding **BLOCK (exit 1)** for that comparison. These counts match the [recorded result](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/retry-demo-n200.md). The [recorded six-step run](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/reports/ci-gate-2026-10-06/logs/hero-demo-2026-10-05.txt) is separate historical evidence. Installation needs network; fixture execution is offline.

Retain the existing transcript as an explicitly labelled excerpt from that recorded run. Add no unmeasured runtime promise.

**5. “What it does not do” additions**

- **Reference validation executes user code.** `arci init` validates Python references by importing them, so import-time code runs.
- **Declaring a fault does not guarantee injection.** A fault naming a tool the agent never calls silently never fires; inspect the recorded calls to confirm injection.

No files changed. Word count and command fidelity checked; runtime and rendering checks were not run.