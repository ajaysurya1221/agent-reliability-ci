# Candidate authentic fixtures for the importer model (memo D2/D3), recorded 2026-10-13 ~18:25Z

Rule (memo D3 acceptance, line 102; kill criterion line 306): fixtures must be authentic, versioned
exports from at least two independent producers; nothing hand-written. Pins below are the default
branch HEAD at the time of recording (read-only `gh api`); a fixture is "in hand" only when its raw
bytes are stored with URL, commit and sha256 next to the importer's test.

| # | Producer (independent of the others) | What | Where (pin) | Status |
|---|---|---|---|---|
| 1 | OpenTelemetry (protocol authors) | `examples/trace.json`: the canonical OTLP/JSON `TracesData` encoding (not GenAI; format fixture for the parser) | `open-telemetry/opentelemetry-proto` main @ ac022ea9db50 (2026-10-13), blob 41130ff1aa0d, 1229 bytes; latest release v1.11.1 (2026-09-29) | candidate; fetch and pin at v1.11.1 |
| 2 | OpenTelemetry GenAI instrumentation (official `opentelemetry-instrumentation-openai-v2`) | GenAI spans produced by the real instrumentation replaying its own VCR cassettes (`tests/cassettes/`) through an OTLP file/console exporter: authentic producer, offline, reproducible; the test expectations (`test_chat_completions.py`, `test_responses.py`) document the attributes | `open-telemetry/opentelemetry-python-contrib` main @ aa5fba1eb4a0 (2026-10-13), `instrumentation-genai/opentelemetry-instrumentation-openai-v2/tests` | candidate; needs a small harness (D3 task) that runs the instrumentation offline and writes OTLP JSON; version = the package's release used |
| 3 | Arize OpenInference instrumentations | OpenInference spans (`openinference.span.kind` = TOOL/LLM/AGENT …) from the real instrumentations' tests; notably `openinference-instrumentation-claude-agent-sdk` (relevant to memo D5) and `-anthropic`, `-openai` | `Arize-ai/openinference` main @ 1198ec958496 (2026-10-12), `python/instrumentation/<package>/tests` | candidate; same offline-replay approach as 2; semantic conventions differ from OTel GenAI (that is the point of two producers) |
| 4 | Langfuse | OTLP export: docs describe the ingestion mapping (`langfuse.com/docs/opentelemetry/example-python-sdk`) but publish no export file | — | not a fixture source without an account/export; ask a Langfuse user (memo target list) when pilots exist |
| 5 | Phoenix (Arize) | Trace export via the Phoenix API/CLI (`ax spans export`); docs "Import Existing Traces" / "Export Data & Query Spans" | — | not public as a file; same as 4 |
| 6 | OpenAI Agents SDK instrumentation (`opentelemetry-instrumentation-openai-agents-v2`) | agent/tool spans from the official OTel instrumentation; candidate for memo D6's "OpenAI OTLP first" | same repo as 2 | candidate |

Decision for this run: D3 does **not** start. Two producers are available offline (2 and 3), which
satisfies the "independent producers" clause without inventing data, but producing the fixtures is
itself a task (a replay harness per instrumentation, pinned package versions, recorded sha256s) and
belongs to the D3 task when it is scheduled. Sources 4 and 5 become available only through pilots
(HUMAN_INBOX section 5).
