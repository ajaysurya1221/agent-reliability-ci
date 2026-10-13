REVIEW 04-05 — Reviewer Astra | Verdict REVISE

Findings by severity:

- **MAJOR — `src/arci/init.py:579`: publication can overwrite without `--force`.** Any non-`FileExistsError` from `os.link` falls back to `os.replace`. On filesystems without hard links, another process can create the destination after the collision check and lose it. A mocked `EOPNOTSUPP` confirmed this overwrite path with `force=False`. Fail closed when atomic no-clobber publication is unavailable. Verify by injecting that failure while creating a competing destination; its bytes must survive and staging must disappear.

- **MAJOR — `src/arci/runner.py:139`; `docs/design/0006-cwd-on-the-child-import-path.md:28`: appending does not guarantee import precedence.** A regular package in appended cwd supersedes earlier namespace-package portions, including bundle contents. A `PathFinder` probe confirmed this. Existing references can therefore resolve differently, changing future trial outcomes and seals despite unchanged record formats. Also, `mcp_boundary.py:775` allows configured `PYTHONPATH` to override the inherited path, contradicting the ADR’s universal claim. ADR 0006 is frozen: the orchestrator must resolve these claims. Verify installed and bundled namespace-package collisions, including grader references and configured MCP environments.

- **MINOR — `src/arci/init.py:591`; `src/arci/cli.py:723`: CLI guarantees are incomplete.** `--out=-review.yaml` produces `arci run -review.yaml`, which the parser rejects; shell quoting does not prevent option interpretation. Use `--` before such paths. Missing required arguments also omit the mandated `init:` prefix; ownership constraints explain this deviation but do not satisfy ADR 0008. Verify the printed command parses successfully and malformed init invocations produce the specified diagnostic prefix.

- **MINOR — `src/arci/descriptor.py:216`: repeated merge keys bypass duplicate rejection.** `task: {<<: {x: 1}, <<: {x: 2}}` silently accepts the second value. This differs from a legitimate explicit override of an inherited key. Reject repeated `<<` entries while allowing `<<: [*a, *b]` and explicit overrides. Verify all three cases; ordinary duplicates and duplicates inside merged mappings already reject correctly.

- **MINOR — `src/arci/cli.py:262`: nondefault thresholds are labelled “default.”** At alpha 0.1/delta 0.2, the notice correctly computes 17/8 but calls those the default rule. Use exactly: **“under this design’s fixed-sample Clopper–Pearson rule”** for in-domain designs. For fallback numbers use: **“for reference only, under Clopper–Pearson with alpha 0.05, delta 0.1, K=1 and one look”**. Verify both messages with nondefault parameters and an out-of-domain design.

Required changes (for REVISE/REJECT):

1. Remove the unsafe no-force replacement fallback; add publication failure/race coverage.
2. Resolve namespace precedence and obtain an orchestrator correction to frozen ADR 0006 before approval.
3. Make leading-dash output paths runnable and restore init diagnostic prefixes.
4. Reject duplicate merge keys without rejecting legitimate merge overrides.
5. Apply the exact statistical wording above.

Follow-ups:

The `.yaml`/`.yml` restriction, `NAME::OCC`, advertised-tools suffix, public helper, and omitted `task_id` are reasonable deviations. Header, quoting, defaults, labels and single-condition fault composition checked correctly. Same-directory staging avoids ordinary cross-device publication; replacing a regular hard-linked destination leaves its other links intact.

The child’s fd redirection passed a real subprocess probe; the parent did not import the fixture. Deadline supervision and group cleanup are structurally sound within the documented process-group boundary. Detached descendants remain excluded. Factory execution with seed 0 is documented, but can produce persistent side effects; correct the unconditional “no descendant outlives” claim at `init.py:399`.

No files changed. Exact-commit `.venv/bin/python -I -B -c …` probes reported **9 statistical checks passed**, **4 output checks passed**, and successful child-output isolation. Default thresholds are **42/8**. Synthetic PASS/BLOCK/INCONCLUSIVE comparisons preserved stdout, decision bytes and exit codes against the parent commit. The supplied diff matches exactly; no frozen files changed. Full filesystem/process acceptance was not rerun: temporary-file creation is sandbox-blocked. Start with the publication fallback at `src/arci/init.py:579`.

