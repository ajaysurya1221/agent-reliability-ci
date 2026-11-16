# awesome-observability: one-line listing

List: https://github.com/adriannovegil/awesome-observability (750 stars; outside pull
requests merged on 6 and 7 Nov 2026). Rules read on 2026-11-16 from the raw
`contributing.md`: "Add one resource per pull request when possible.", entries as
"- [Name](https://example.com/) - Short, factual description.", and not for "Very early
projects without enough information for readers to evaluate them." No rule on stars, age
or who may submit.

Section: `## 10. LLM & AI Observability`, `### Cost & Usage Tracking`, last line, after
Caprock. The section already lists tools that read local Claude Code and Codex session
files (Aether, agenttrace, Caprock) and one that compares an agent's behaviour between two
runs (whatbroke).

## Prepared

Fork `ajaysurya1221/awesome-observability` (created 2026-11-16), branch `add-realornoise`,
commit `a57e5f6`, one line added, based on the list's current `master`:

```markdown
- [realornoise](https://github.com/ajaysurya1221/agent-reliability-ci) - Local Python CLI that reads Claude Code and Codex session logs and compares recent days with earlier days on recorded measures such as reasoning tokens per response and failed file edits. Prints REAL DROP, NO DROP or CANNOT TELL; with a short history the usual answer is CANNOT TELL. Runs no model and sends nothing. It does not show a cause or answer quality. Apache-2.0.
```

## To open it

Link (title filled in): https://github.com/adriannovegil/awesome-observability/compare/master...ajaysurya1221:awesome-observability:add-realornoise?expand=1&title=Add%20realornoise%20to%20LLM%20%26%20AI%20Observability

The list's template asks for a Summary and a checklist. Summary to paste:

```markdown
- Adds realornoise to 10. LLM & AI Observability, Cost & Usage Tracking, after Caprock.
- It is a local Python CLI that reads Claude Code and Codex session logs, compares recent days with earlier days, and prints REAL DROP, NO DROP or CANNOT TELL. It runs no model and sends nothing, and it does not show a cause or answer quality.
- I maintain the project (Apache-2.0, version 2.4.0 on PyPI since 16 Nov 2026). With a short history its usual answer is CANNOT TELL.
```

Checklist: the first four boxes are true of this change (one resource, the fitting section,
a short factual description, a canonical public link that works). Leave "I ran `make lint`
locally" unticked: it needs Docker and was not run; the list's CI runs it on the pull
request.

## Risk

With 0 stars the list's maintainer may read the project as "very early". The repository
has documentation, a release history and tests; the decision is theirs.
