# ARCI forward plan: from rigorous core to ten-minute first verdict

## Executive summary

**Ship v0.8.0 by 20 October 2026 around distribution and comprehension, not new statistical machinery:** publish the existing wheel to PyPI, make `uvx --from agent-reliability-ci arci demo` work without cloning, add one thin declarative front-end generated from the existing Pydantic schema, ship `arci init`, rewrite the README first screen, and include the already-landed `arci plan`, opt-in `pass^k`, and portability fixes. ARCI already has the hard part—the sealed experiment, four-way gate, MCP boundary, diagnosis and replay—and the packaging metadata already defines a Hatch wheel and `arci` console script. fileciteturn7file0 fileciteturn2file0

**Spend the following 30 days on one durable integration seam: OpenTelemetry/OTLP.** OpenTelemetry’s GenAI semantic conventions and OTLP are now broad interchange points, while Langfuse, Phoenix and LangSmith all have OTel/OTLP paths; this avoids three observability-specific importers. Import traces for analysis first; never turn retrospective traces into a pre-registered PASS. citeturn3search0turn3search1turn22search0turn22search6

**Spend the remainder of the 90 days proving external use, then add provider-specific session ingestion only behind that common importer seam.** Claude hooks/stream JSON and Codex App Server/OTLP are useful data sources; broad “SDK adapters”, another MCP conformance client, a general chaos framework, a new record/replay system and a general observability UI are not. Official SDKs, MCP Inspector, agent-chaos and Chronicle already occupy those wheels. citeturn4search0turn9search2turn10search0turn18search0

**Today’s estimated own-agent time-to-first-verdict is 60 minutes, with a plausible 45–90 minute range; this is an UNVERIFIED planning estimate, not measured user data.** The current path requires cloning, synchronising a development environment, understanding a Python manifest builder and adapting an oracle/toolset before a first own-agent experiment. The target is **≤10 minutes to the first valid verdict on a fast existing agent, including an honest `INCONCLUSIVE`, and ≤2 minutes to the packaged demo**. fileciteturn2file0

**The first three sprint tasks are:** publish/install packaging; make the recorded demo self-contained under `uvx`; then add the declarative manifest descriptor plus generated JSON Schema. `arci init` comes immediately after those three because it should emit that descriptor rather than create a second configuration engine.

## Wheel map

ARCI should position itself as the **pre-registered reliability gate and reproducer**, not as another general-purpose evaluation framework. Its own technical report already correctly distinguishes it from evalsig, Chronicle, agent-chaos, AgentChaos/AGENTCHAOSBENCH, Promptfoo, Inspect AI, Braintrust, LangSmith and Langfuse; the table below extends that comparison into specific integration choices rather than repeating it. fileciteturn6file0

| Capability / existing wheel | Maintainer, adoption and recency | Licence / last release or dated state | Exact overlap with ARCI | Decision | Exact integration point |
|---|---|---|---|---|---|
| **evalsig** | `vtensor`; small project: 2 stars, created May 2026. fileciteturn20file0 | Apache-2.0; no release verified; last push 17 May 2026. fileciteturn20file0 | Power planning, three-way gates, paired/clustered inference and monitoring overlap ARCI’s statistical layer. fileciteturn6file0 | **Compete narrowly / ignore at runtime** | Keep ARCI’s frozen gate. Cite evalsig when explaining alternatives. Do not make the gate depend on another package. |
| **Promptfoo + Promptfoo Action** | Promptfoo; about 25.7k GitHub stars in the October 2026 snapshot; repeated-success issue #5947 shows direct demand. citeturn12search4 fileciteturn6file0 | MIT; main CLI 0.124.x active in October 2026; GitHub monorepo also released code-scan-action 0.2.2 on 8 Oct. citeturn12search2 fileciteturn22file0 | General LLM evaluation, assertions, matrices, regression CI. Its repeated-success work overlaps consistency metrics, not ARCI’s sealed fault experiment + exact four-way gate + replay. | **Integrate socially, do not absorb evaluator features** | Recipe: run Promptfoo for its evaluation use cases; use ARCI where the unit is baseline-vs-candidate reliability under predeclared faults. Do not ingest an arbitrary Promptfoo score into ARCI and call it pre-registration. |
| **Inspect AI** | UK AI Security Institute; active 2026 agent-eval ecosystem. Recent issues cover scorer crashes, provider-schema problems and proof of completion for tool-using agents. citeturn11search14turn11search15turn11search17 | Open-source; GitHub release mechanism not used; an August issue referenced Inspect 0.3.258 on 11 Aug 2026. Exact current package release on 13 Oct is **UNVERIFIED**. citeturn11search16 | Tasks, solvers, tools, scorers, logs and sandboxes overlap execution/evaluation. ARCI’s prospective rule binding, injected boundary faults and exact replay are different. | **Integrate through recipes, not adapter framework** | Show an Inspect-produced agent command behind ARCI’s MCP boundary when the tools can be routed there. Leave Inspect scoring/sandboxing intact. |
| **DeepEval** | Confident AI; large active evaluation project, with 4.x active in 2026 and Jev/System One-related evaluation support in 4.2.x. citeturn12search7 | Apache-2.0; exact 13 Oct release date **UNVERIFIED**. | Evaluation metrics/test cases overlap generic agent evaluation. agent-chaos can already integrate DeepEval. citeturn10search0 | **Ignore at core** | Cookbook interoperability only. Do not add LLM-as-judge/scorer infrastructure. |
| **Pydantic Evals / Pydantic AI** | Pydantic; v2 stable from June 2026 and v2.51.0 released 25 Sep 2026. Its users explicitly requested stronger framework-level testing utilities in issue #3138. citeturn12search9turn12search0turn13search1 | MIT; v2.51.0, 25 Sep 2026. citeturn12search0 | Dataset/evaluator framework and deterministic test models overlap generic testing, not ARCI’s reliability contract. Pydantic Evals already serialises YAML/JSON and generates JSON Schema. citeturn13search0turn13search2 | **Integrate design pattern; no runtime dependency** | Generate ARCI JSON Schema directly from ARCI’s existing Pydantic models, just as Pydantic Evals does. Keep Python builder as escape hatch. |
| **OpenAI Agents SDK test utilities** | OpenAI; official SDK provides `ScriptedModel` and deterministic provider-neutral test utilities. citeturn4search0 | Official open-source SDK; exact latest release/date on 13 Oct **UNVERIFIED**. | Deterministic orchestration/model tests overlap any proposed ARCI SDK fake. The docs explicitly distinguish those tests from real-provider behaviour. citeturn4search0 | **Integrate; never rebuild** | Recipe can use SDK test models inside an arm for deterministic fixtures, while ARCI owns repeated baseline/candidate scheduling and boundary faults. |
| **Claude Agent SDK / Claude Code hooks** | Anthropic; active SDK, with late-September/early-October 0.3.x releases. Public 19 Mar 2026 issue #701 reported repeatable hangs after tool calls. citeturn15search4turn15search13 | SDK licence/release-day exactness **UNVERIFIED**; current series 0.3.x is verified. | Native sessions, hooks and agent lifecycle overlap instrumentation, not statistical gating. Python hooks include PreToolUse/PostToolUse/Stop and related events. citeturn21search2 | **Integrate as data source** | First prefer hooks/official stream output into the common importer. Do not monkey-patch the SDK. Imported history is analysis-only until a new prospective ARCI experiment is sealed. |
| **Google ADK / Agents CLI evaluation** | Google; Agents CLI evaluation reached GA in 2026 and generated projects include evaluation datasets/config. citeturn14search8turn14search9 | Apache-2.0 for ADK; exact current release **UNVERIFIED**. | Agent execution, traces and eval grading overlap a generic evaluator. | **Integrate via command/trace recipes** | Run ADK agents as command arms when tools pass through ARCI; otherwise consume traces through OTel for analysis. |
| **Microsoft Agent Framework evaluation** | Microsoft; provider-agnostic `EvalItem`, evaluators and results are documented in 2026. citeturn5search15 | Open-source framework; exact latest package release **UNVERIFIED**. | Evaluation abstraction overlaps scorers and result aggregation. | **Ignore at core / recipe only** | An Agent Framework program is an ARCI command arm; keep its evaluators separate. |
| **OpenTelemetry GenAI semantic conventions + OTLP** | OpenTelemetry/CNCF; current snapshots show Semantic Conventions 1.44.0, core spec 1.61.0 and OTLP 1.11.0. GenAI conventions cover messages, tools and MCP-related signals. citeturn3search3turn22search4 | Apache-2.0; current versions above as of Oct 2026. | Standardises trace interchange, not reliability decisions. | **Integrate first** | `arci import otlp` consumes OTLP JSON first, then protobuf; maps GenAI/MCP spans into an immutable analysis record with explicit provenance/completeness. |
| **Langfuse** | Langfuse; v4 is OTel-native and its public endpoint accepts OTLP. Legacy ingestion has a 16 Nov 2026 sunset. citeturn2search0turn2search3 | Open-source/cloud licensing specifics are **UNVERIFIED** here; v4 GA is current. | Trace store, experiments, evaluation and observability overlap reporting—not ARCI gating. | **Integrate through OTLP only** | No Langfuse importer. Export/fetch OTLP and feed the generic ARCI importer. |
| **Arize Phoenix / OpenInference** | Arize; Phoenix supports OTel-based tracing and a wide range of agent frameworks; it can itself run via `uvx`. citeturn22search0 | Licence detail **UNVERIFIED** in this pass; current repository checked Oct 2026. | Trace storage, replay/playground and evaluation overlap observation/analysis. | **Integrate through OTel/OpenInference** | Accept OpenInference/OTLP spans; translate known OpenInference GenAI attributes at the importer edge, not in gate logic. |
| **LangSmith OTel ingest** | LangChain; its collector proxy accepts standard OTLP JSON and protobuf. A June 2026 issue discusses OTel-ingested spans explicitly. citeturn22search6turn22search5 | Hosted service plus open-source SDK/components; exact current SDK release **UNVERIFIED**. | Trace store/evaluation overlaps observability. | **Integrate through OTLP only** | Same `arci import otlp`; no LangSmith-specific trace database client in core. |
| **agent-chaos** | Deepankar/agent-chaos; active 2026 project; about 34 stars in the checked snapshot. Supports model errors/timeouts/stream faults and tool errors/timeouts/mutations. citeturn10search0 | Apache-2.0; exact current release date **UNVERIFIED**. | Large overlap with expanding ARCI into a general chaos/fault catalogue. | **Integrate conceptually; do not rebuild** | Keep ARCI’s small deterministic fault set. Document custom faults and, later, a translation layer only where an agent-chaos scenario has deterministic ARCI semantics. |
| **AgentChaos / AGENTCHAOSBENCH** | 2026 research: AgentChaos studies non-intrusive LLM-boundary fault injection; AGENTCHAOSBENCH spans tool, model, guardrail and inter-agent faults. citeturn10academia27turn10academia24 | Papers dated 7 and 4 Aug 2026; software licence not applicable here. | Shows that a broad HTTP/model/inter-agent chaos expansion is already an active field. | **Ignore as product surface; use taxonomy evidence** | Cite fault categories when deciding which custom fault recipes matter. Do not turn ARCI into a proxy-chaos platform. |
| **MCP Inspector** | Model Context Protocol project; 11,060 stars / 1,541 forks in GitHub metadata on 13 Oct; actively pushed 12 Oct. fileciteturn15file0 | GitHub API reports licence `NOASSERTION`; v2.10.1 released 8 Oct 2026. fileciteturn23file0 | Visual/CLI/TUI MCP server testing, debugging and protocol checks overlap any proposed ARCI MCP tester. citeturn9search2 | **Integrate; hard no-build on conformance UI/client** | Cookbook/CI preflight invokes Inspector’s CLI first; ARCI then tests stochastic behaviour under injected tool faults. |
| **Chronicle** | The Agent Plane; 25 stars, 6 forks, active push 12 Oct 2026. fileciteturn21file0 | MIT; no tagged latest release verified; repository active through 12 Oct. fileciteturn21file0 | Records decision graphs, supports cut-point replay and OTel IDs—high overlap with proposed counterfactual replay. citeturn18search0 | **Integrate later; drop ARCI counterfactual-replay build** | Explore conversion at ARCI `RecordedCall`/trace-event ↔ Chronicle envelope level. Preserve ARCI’s stricter exact-consumption replay for verdict evidence. |
| **VCR.py / pytest-recording** | Mature Python HTTP recording ecosystem; roughly 3k and 600+ stars respectively. citeturn18search1turn18search2 | MIT; VCR.py 8.2.1 includes the 2026 unsafe-YAML security fix. citeturn18search3 | HTTP cassette replay overlaps only if ARCI starts recording arbitrary HTTP. | **Ignore in core** | May be used in provider-adapter tests, pinned safely; never substitute a VCR cassette for ARCI’s sealed tool-boundary recording. |
| **Codex App Server / OpenAI session OTLP** | OpenAI; App Server is the JSONL/JSON-RPC harness used across Codex clients, and OpenAI session traces can be exported as OTLP JSON. citeturn8search3turn21search4 | OpenAI Codex open-source components; exact Oct release **UNVERIFIED**. App Server architecture source is dated 4 Feb 2026. | Session/event data overlaps an importer, not the gate. | **Integrate as data source after OTLP** | Prefer OpenAI’s OTLP export or App Server protocol. Do **not** make roadmap claims depend on unverified `codex --json` behaviour. |
| **SciPy statistics** | SciPy community; mature reference statistical library. | BSD-3-Clause; SciPy 1.18.1 published 21 Aug 2026. fileciteturn16file0 | Can compute conventional binomial statistics, but ARCI has a sealed binary64 implementation whose exact bytes matter to historical evidence. | **Use only as test oracle** | Add differential/reference tests where appropriate. Do not replace ARCI’s frozen gate implementation casually. |
| **Randomness guidance + tau2/tau3 benchmarks** | *On Randomness in Agentic Evals* analysed 60,000 SWE-bench trajectories and recommends repeated independent trials/power analysis; Anthropic found infrastructure changes could move Terminal-Bench 2.0 by six points; tau exposes repeated-trial `pass^k`-style metrics. citeturn16academia48turn16search6turn17search1 | Paper rev. 23 Mar 2026; Anthropic 5 Feb 2026; tau2/tau3 v1.0.1 22 Jul 2026. citeturn17search0 | Validates the problem—variance, repeated runs, infrastructure sensitivity—but does not supply ARCI’s prospective CI contract. | **Integrate as methodological guidance** | Cite in docs; keep `pass^k` descriptive and keep sample-size choice prospective through `arci plan`. |

The central architectural consequence is straightforward: **OTLP is the durable interoperability boundary; MCP Inspector is the protocol preflight; official SDK utilities remain the unit-test layer; ARCI remains the prospective reliability experiment.** OTel is a substantially safer 12–24 month bet than custom Langfuse/LangSmith/Phoenix adapters because all three already intersect the OTel ecosystem. citeturn2search3turn22search0turn22search6

ARCI should also resist pressure to become statistically “feature-complete”. Its current conservative gate can be inconclusive even for material-looking empirical differences: in the committed operating-characteristic table, a true 0.95→0.75 drop blocks only about 36.5% of N=200 fixed-sample Clopper–Pearson experiments; that behaviour is deliberate and exposed by `arci plan`. fileciteturn6file0 The project already supports more than the situation summary implies—Newcombe and frozen finite sequential looks are documented—but the default exact rule remains the clearest public contract. fileciteturn9file0

## Candidate bets

Scores are **Demand / Non-duplication / TTFV impact / Design fit / usable in seven days / 12–24 month durability**, each 1–5 except the required hard-gate **0** where a maintained tool already covers at least roughly 80% of the proposed feature.

| Bet | Scores | Evidence and reasoning | Decision |
|---|---:|---|---|
| **PyPI package + `uvx` demo** | **5 / 5 / 5 / 5 / 5 / 4 = 29** | ARCI already has Hatch wheel metadata and a console entry point, so this is distribution, not a rebuild. `uvx` is explicitly designed to run a package in an isolated environment without a persistent install. fileciteturn7file0 citeturn11search3 | **SHIP v0.8.0** |
| **`arci init` scaffold** | **5 / 5 / 5 / 5 / 4 / 5 = 29** | Every celebrated onboarding comparator scaffolds or immediately runs something: `uv init`, Promptfoo init, Playwright init, `k6 new`. ARCI currently sends users to a Python manifest example. citeturn20search2turn20search1turn20search5turn19search0 | **SHIP v0.8.0** |
| **Declarative YAML + generated JSON Schema** | **4 / 4 / 5 / 4 / 4 / 5 = 26** | ARCI models are already immutable Pydantic models; Pydantic Evals demonstrates the maintainable pattern of serialised configs plus generated JSON Schema. fileciteturn14file0 citeturn13search0 | **SHIP, but only as a thin front-end** |
| **Reliability recipes cookbook** | **5 / 5 / 5 / 5 / 5 / 4 = 29** | The missing path is from “interesting project” to “my agent”; no new engine is required. | **SHIP first two recipes v0.8.0; third by 12 Nov** |
| **OTLP GenAI importer** | **5 / 5 / 3 / 4 / 3 / 5 = 25** | OTel GenAI conventions are active and multiple observability systems accept/export OTel/OTLP. citeturn3search1turn2search3turn22search0turn22search6 | **BUILD in 30-day plan, analysis-only first** |
| **Claude/Codex session importers** | **4 / 4 / 3 / 4 / 3 / 3 = 22** | Claude exposes hooks; Codex has App Server and OpenAI OTLP session export. Format churn makes direct vendor parsing less durable than OTLP. citeturn21search2turn8search3turn21search4 | **BUILD only behind common importer layer** |
| **First-class test adapters for every major agent SDK** | **4 / 0 / 3 / 3 / 2 / 2 = DROP** | OpenAI, Pydantic, Google and Microsoft already provide their own testing/evaluation abstractions. A generic ARCI test-double layer would duplicate maintained functionality. citeturn4search0turn13search2turn14search8turn5search15 | **DROP; convert to recipes and trace hooks** |
| **Reliability gating for MCP servers themselves** | **4 / 3 / 2 / 2 / 1 / 5 = 17** | Inspector covers conformance/debugging, but not prospective baseline-vs-candidate reliability under injected faults. However, ARCI currently treats the server as environment and the agent as the changing arm; forcing server-version comparison into that schema would distort semantics. fileciteturn14file0 citeturn9search2 | **90-day design experiment only** |
| **HTML report + PR comment + badge** | **3 / 1 / 2 / 4 / 4 / 2 = 16** | ARCI already writes Markdown to `$GITHUB_STEP_SUMMARY`, while observability/evaluation platforms already provide rich UIs. fileciteturn8file0 | **DROP bundle. Keep existing summary; add artifact link only if users ask** |
| **Native Windows support** | **3 / 5 / 2 / 3 / 2 / 5 = 20** | Distribution tooling supports Windows, but ARCI’s process-group/stdio guarantees are POSIX-shaped. Packaging compatibility and execution semantics must not be conflated. fileciteturn10file0 citeturn19search12 | **Conditional 90-day bet** |
| **Per-request pacing through parent IPC** | **4 / 5 / 1 / 5 / 4 / 5 = 24** | This fixes a documented correctness limitation for several decisions per trial rather than adding surface area. fileciteturn3file0 | **HIGH PRIORITY immediately after v0.8.0** |
| **Counterfactual replay** | **4 / 0 / 1 / 3 / 2 / 2 = DROP** | Chronicle already provides cut-point replay of recorded agent decision graphs, giving this proposed feature ≥80% conceptual overlap. citeturn18search0 | **DROP implementation; investigate Chronicle interop** |
| **Permission-decision calibration** | **2 / 5 / 1 / 4 / 3 / 3 = 18** | Fits existing Jev calibration work but has no external user evidence yet; current published audit is intent-routing, not coding permission decisions. fileciteturn3file0 | **DEFER until labelled external use case exists** |

The score ordering makes the development thesis unusually clear: **distribution, scaffolding and recipes outrank new research features because ARCI currently has no external users.** Adding more statistical or replay sophistication before making the existing experiment usable in ten minutes would optimise the wrong constraint.

The broad SDK-adapter bet and counterfactual-replay bet fail the non-duplication hard gate. MCP-server gating does **not** fail that gate—Inspector is not a stochastic regression gate—but it fails short-term design fit because ARCI’s `McpServerSpec` is currently the environment behind the agent, not one of the two comparison arms. fileciteturn14file0

## Sequenced development plan

The estimates below are implementation-budget estimates for one developer using two coding agents. They are not promises about unattended elapsed time.

**Seven-day sprint — 13–20 October 2026; release target: v0.8.0.**

| ID | Task | Goal and acceptance criterion | Est. | Depends on | Reuses | External integration |
|---|---|---|---:|---|---|---|
| **S1** | **Publishable package pipeline** | Build wheel+sdist from the existing Hatch config, publish via PyPI trusted publishing, install in clean Python 3.11 and 3.14 environments. Acceptance: `uv tool install agent-reliability-ci && arci --help` works with no checkout. | 4h | none | `pyproject.toml`, existing console script | PyPI, `uv build`/`uv publish` |
| **S2** | **Packaged `arci demo`** | Move the existing recorded retry demo onto packaged resources/API calls. Acceptance: `uvx --from agent-reliability-ci arci demo` runs from an empty directory, makes no model call, exercises the real gate/diagnosis/replay path and exits as documented in ≤2 min on reference Ubuntu/macOS machines. | 5h | S1 | retry-agent fixture, CLI, bundle/replay code | `uvx` |
| **S3** | **Declarative descriptor + generated JSON Schema** | Add `arci.yaml` as a thin deserialisation layer into the existing Pydantic `Manifest`, then seal canonical JSON exactly as today. Acceptance: descriptor→Manifest→sealed JSON and equivalent Python builder produce the same semantic manifest; no decision logic exists in the YAML layer; schema is generated from code. | 7h | none | `arci.schema.Manifest`, Pydantic | JSON Schema tooling / Pydantic pattern |
| **S4** | **`arci init`** | Scaffold a real experiment instead of making newcomers author `Manifest.create`. Acceptance: one non-interactive command accepting experiment name, baseline ref, candidate ref, toolset ref and oracle ref writes a schema-valid descriptor that runs without hand-editing syntax. | 8h | S3 | existing schema/defaults | onboarding pattern from uv/Promptfoo/Playwright |
| **S5** | **Honest smoke-design UX** | Keep the first run fast without pretending it is confirmatory. Acceptance: generated descriptor uses a small explicitly labelled smoke N; CLI prints that small N usually yields `INCONCLUSIVE`, and points to `arci plan` before CI-scale execution. No automatic outcome-dependent extension. | 3h | S4 | unreleased `arci plan`, existing gate | randomness/sample-size guidance |
| **S6** | **README first-screen replacement** | Put the value proposition and two commands before statistics jargon. Acceptance: first screen follows the exact order below; ≤200 words before deeper docs; relative PASS and “not a sandbox” remain visible before the fold. | 4h | S2, S4 | current hero evidence and figure | onboarding patterns from five comparator tools |
| **S7** | **Python-agent recipe** | “Gate a retry-policy change in ten minutes.” Acceptance: from a blank sample project, the recipe requires only four user-specific refs plus task data and reaches a valid verdict; no copied gate/statistics code. | 3h | S4 | Python agent interface, retry example | official SDK test utilities remain optional |
| **S8** | **MCP command-agent recipe + Inspector preflight** | Give MCP authors/agent builders a complete route using what already exists. Acceptance: recipe invokes Inspector for protocol/tool discovery and ARCI for recorded/faulted repeated trials; docs explicitly distinguish the two. | 4h | S4 | MCP shim/boundary, `McpServerSpec` | MCP Inspector |
| **S9** | **TTFV and cold-read measurement harness** | Replace estimates with measurements. Acceptance: fresh-machine checklist records install start, scaffold complete, run start, verdict and interpretation answer; five cold readers can be scored without maintainer coaching. | 3h | S2, S4, S6 | examples/tests | none |
| **S10** | **Release-integrity merge** | Incorporate already-unreleased `arci plan`, opt-in `--pass-k` and portability fixes. Acceptance: CHANGELOG identifies them as v0.8.0; old decision re-derivation and default report bytes remain pinned as appropriate. | 4h | main clean | existing unreleased work | none |
| **S11** | **Install and Action matrix** | Ensure distribution did not break CI use. Acceptance: wheel install and Action fixture pass on Ubuntu/macOS; Windows runs install/import/`--help` smoke only and is explicitly *not* advertised as supported execution. Existing Action still appends the Markdown gate report to the job summary. | 3h | S1, S10 | `action.yml`, existing CI | GitHub Actions, PyPI |
| **S12** | **v0.8.0 release and evidence receipt** | Produce the release users will actually install. Acceptance: immutable tag, PyPI files, SHA256s, release note with exact commands, recorded fresh-machine demo timing, Action tag, and no claims beyond the existing trust model. | 3h | S1–S11 | release/evidence practices already used in repo | GitHub Releases, PyPI |

Total planned implementation budget: **51 hours**.

The smoke scaffold should use a very small predeclared N—five pairs is a reasonable starting implementation choice—not because five trials prove reliability, but because the product objective is first contact with the real machinery. ARCI’s own statistics documentation already says N=20 is exploratory and can remain overwhelmingly inconclusive; a five-pair run should therefore be labelled **SMOKE / EXPECT INCONCLUSIVE** even more strongly. fileciteturn9file0 The user then runs `arci plan` and seals a confirmatory N before collecting confirmatory data. This distinction is non-negotiable.

**Thirty-day plan — complete by 12 November 2026.**

| ID | Task | Goal and acceptance criterion | Est. | Depends on | Reuses | Integrates with |
|---|---|---|---:|---|---|---|
| **D1** | Parent-IPC per-request pacing | Replace divide-by-k trial-start approximation. Acceptance: multi-decision concurrent tests prove aggregate admitted requests respect the declared rate without altering outcome classification. | 10h | v0.8.0 | decision boundary/parent runner | Jev/live provider limits |
| **D2** | Import-record provenance model | Define one immutable imported-session schema with source, original IDs, completeness, raw digest and capability flags. Acceptance: record cannot masquerade as a scheduled ARCI trial. | 6h | v0.8.0 | hashing/schema primitives | OTel/provider logs |
| **D3** | OTLP JSON importer v1 | Parse GenAI/MCP spans into analysis records. Acceptance: authentic versioned fixtures from at least two independent producers map to calls/events; unsupported or incomplete semantics stay explicit. | 12h | D2 | events/diff representation | OTel GenAI, OTLP |
| **D4** | OTLP protobuf path | Add protobuf input only after JSON semantics stabilise. Acceptance: JSON/protobuf versions of one fixture produce equivalent normalised records. | 8h | D3 | same importer | OTLP protobuf |
| **D5** | Claude analysis importer | Consume official Claude hook/session output through the common importer model. Acceptance: versioned fixture from a real Claude session imports without monkey-patching; data remains analysis-only. | 10h | D2 | importer model | Claude Agent SDK/Claude Code hooks |
| **D6** | Codex analysis importer | Prefer OpenAI OTLP session export; add App Server JSONL only where OTLP lacks required information. Acceptance: authentic fixture, version pinned, no dependency on UNVERIFIED `codex --json`. | 10h | D2, D3 | importer model | OpenAI Agents/Codex |
| **D7** | Third reliability recipe | Publish “LangGraph/Pydantic-style bot under a transient tool fault”, using framework-native test utilities where useful and ARCI only for the repeated gate. | 6h | v0.8.0 | command/Python arms | LangGraph or Pydantic AI |
| **D8** | External pilot round | Recruit the first five target users below. Acceptance: at least one complete external recorded run or a written blocker from every participant; no undocumented maintainer intervention hidden from the TTFV measurement. | 6h maintainer | S9 | recipes | target communities |

An imported production trace should support **diffing, cohort discovery and manifest drafting**, but cannot retrospectively become a valid ARCI gate record. The gate requires the rule, schedule, seeds and experiment identity to have been fixed before execution; changing that would destroy the project’s differentiator. fileciteturn9file0

**Ninety-day roadmap — complete by 11 January 2027.**

| ID | Task | Goal and acceptance criterion | Est. | Depends on | Reuses | Integrates with |
|---|---|---|---:|---|---|---|
| **R1** | OTLP importer hardening | Support authentic fixtures from OTel-native paths across at least Langfuse plus one of Phoenix/LangSmith, with explicit unsupported-field reporting. | 16h | D3/D4 | importer | OTLP ecosystem |
| **R2** | External evidence cohort | Reach ten external users and preserve both successful and failed onboarding records. Acceptance: ≥5 external recorded runs from ≥3 independent repositories; no run rewritten to look successful. | 16h maintainer | D8 | measurement harness | communities below |
| **R3** | Chronicle interop spike | Demonstrate conversion of one ARCI recorded boundary trace into a Chronicle-compatible record, or document a concrete semantic incompatibility. No new ARCI replay mode. | 8h | D2 | boundary records | Chronicle |
| **R4** | MCP-server reliability design record | Determine whether “server A vs server B” can be represented without redefining the trusted environment/oracle contract. Acceptance: design record plus one prototype experiment; no public feature unless semantics stay honest. | 10h | external MCP pilot | MCP boundary | Inspector |
| **R5** | Native Windows decision | Run process/stdio/cleanup semantics on Windows. Acceptance: full support only if timeout, child cleanup, MCP stdio, path sealing and replay invariants meet the same tests; otherwise document WSL and keep native Windows unsupported. | 12h | S11 | portability suite | Windows/Python/uv |
| **R6** | Permission calibration decision | Proceed only with a versioned external labelled permission dataset and a real user. Acceptance if built: separate preregistered protocol; no inference from the existing intent-routing audit. | 12h conditional | external demand | Jev audit framework | coding-agent permission data |
| **R7** | Resume/index evidence gate | Add SQLite/resumability only if two independent real runs are lost/expensive enough to make interruption a documented problem. If triggered, SQLite indexes records; JSON/sealed records remain evidence source. | 12h conditional | external evidence | run stores | SQLite |
| **R8** | Reporting decision | Add HTML or PR-comment UX only after ≥3 external users independently ask for richer presentation than the current GitHub Step Summary. Never make HTML the canonical evidence. | 8h conditional | R2 | Markdown report/Action | GitHub |

This leaves the roadmap’s cohort-localisation idea behind the 90-day critical path. It is interesting, but external usage and trace interoperability are stronger current constraints than another diagnosis algorithm. The same applies to a larger perturbation library: agent-chaos and the 2026 AgentChaos work demonstrate that the catalogue can expand indefinitely; ARCI should add a fault only when it has a reproducible contract and a user case. citeturn10search0turn10academia27

## Comprehension audit and time-to-first-verdict

This is a **cold-read desk audit**, not a human-subject result: I evaluated only what each persona can recover from the current README in the specified time window. The sprint measurement task must replace these heuristic scores with actual readers. The current README does several things unusually well—it opens with a concrete retry regression and puts “PASS means relative non-inferiority, not absolute reliability” near the top—but the own-agent route does not appear as three executable commands; instead, the first runnable path is a repo clone and six-stage fixture, followed later by a pointer to a Python manifest builder. fileciteturn2file0

| Persona | What is it? | For whom? | What does PASS mean? | What does it *not* do? | First three own-agent commands? | Score / failure point |
|---|---:|---:|---:|---:|---:|---|
| Curious developer, 60 s | 4 | 3 | 5 | 4 | 0 | **3.2/5.** Concrete hero works; fails at “Use the example’s manifest builder as the starting point”. That is guidance, not a runnable own-agent path. |
| Agent builder, 5 min | 5 | 4 | 5 | 5 | 1 | **4.0/5.** Understands design; must reverse-engineer `examples/retry_agent/experiment.py` to start. |
| MCP server author | 3 | 2 | 4 | 4 | 0 | **2.6/5.** README explains an MCP server as ARCI’s environment, but does not answer “can I regression-gate my server?” |
| Platform / CI engineer | 4 | 4 | 5 | 5 | 2 | **4.0/5.** Action and exit codes are good; prerequisite manifest creation remains the missing step. |
| ML researcher | 5 | 3 | 5 | 5 | 1 | **3.8/5.** Statistical contract is unusually clear, but onboarding front-loads implementation concepts before the minimum experiment. |

The jargon audit should aggressively distinguish **first-screen language** from **technical-document vocabulary**.

| Current term | First-use language | First screen? |
|---|---|---|
| oracle | **independent success check** — code outside the agent decides whether the task really succeeded | Keep only plain phrase |
| contract | **observable behaviour rules** | Remove term |
| arms | **baseline and candidate versions** | Remove term |
| conditions | **test scenarios** | Prefer replacement |
| falsify bucket | fault the agent is expected to survive | Remove |
| benign bucket | harmless change that should not alter behaviour | Remove |
| ceiling bucket | known-unsurvivable scenario, recorded but not gated | Remove |
| alpha | maximum statistical error budget used by the gate | Remove |
| delta | **allowed reliability drop** | Define once; hide Greek letter initially |
| non-inferiority | **candidate is not shown to be worse than baseline by more than the allowed drop** | Use plain sentence |
| Clopper–Pearson | exact binomial confidence interval construction | Remove |
| Bonferroni | correction that keeps the total error budget bounded across conditions | Remove |
| ddmin | **fault minimisation** — repeatedly removes injected faults while preserving the same failure | Remove acronym |
| bundle | **replay package** containing the reproducer and recording | Rename on first screen |
| seal | integrity hash tying the declared experiment and records together | Remove |

The first-screen comparison explains the onboarding gap:

| Tool | What its first minutes do | ARCI gap |
|---|---|---|
| **uv** | `uvx` runs a tool in an isolated environment; `uv init` creates a project. citeturn11search3turn20search2 | ARCI currently makes installation start with `git clone`. |
| **Ruff** | Gives an immediate no-install command such as `uvx ruff ...`; value is experienced before configuration. citeturn20search0 | ARCI demonstrates value, but only after checkout/sync. |
| **Promptfoo** | `npx promptfoo@latest init --example ...` creates a runnable example, then users evaluate/view. citeturn20search1turn20search3 | ARCI has no scaffold. |
| **Playwright** | `npm init playwright@latest` creates tests/config and can include CI; the next command runs tests and produces a report. citeturn20search5turn20search8 | ARCI asks the reader to understand the manifest builder first. |
| **k6** | `k6 new` creates the smallest test, then `k6 run` runs it. citeturn19search0turn19search1 | ARCI lacks a “smallest real experiment” command. |

The pattern is not “simpler tools have less theory”; it is **they defer theory until after the first successful interaction**.

The proposed first screen, under 200 words:

> **Did this change make your agent less reliable?**
>
> ARCI runs your baseline and candidate repeatedly under the same predeclared conditions, then returns `PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR` and can replay a recorded failure.
>
> ```bash
> uvx --from agent-reliability-ci arci demo
> ```
>
> ```bash
> uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
> ```
>
> `baseline + candidate → same frozen tasks/faults → repeated trials → verdict → minimise/replay`
>
> **PASS means only this:** on this predeclared experiment, the candidate was not shown to be worse than the baseline by more than the allowed drop. It is **not** a claim of absolute reliability.
>
> A small first run will often be **INCONCLUSIVE**. That is a valid result; use `arci plan` before choosing a larger confirmatory run.
>
> ARCI observes calls that cross its tool boundary. It is not a sandbox, it does not replay model inference, and trace divergence shows where runs differ—not why.

The **two first-screen commands** are therefore exactly:

```bash
uvx --from agent-reliability-ci arci demo
```

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml
```

The second command necessarily contains project-specific Python references; the scaffold should validate those references immediately and fail with one actionable error rather than generating a manifest that dies later.

**TTFV measurement.** Start the stopwatch when a fresh user opens the README on a machine with Python/uv but no ARCI checkout. Stop only when: the terminal has printed a syntactically and semantically valid ARCI verdict; the record validates; and the user can correctly answer “what does this verdict mean?” Record install time, scaffold time, first-run time and interpretation separately. For own agents, report agent execution time separately because ARCI cannot promise a ten-minute wall clock for an agent whose individual calls take minutes.

Today:

| Measure | Today | Target |
|---|---:|---:|
| Demo TTFV | **~8 min UNVERIFIED estimate** | **≤2 min p50**, ≤3 min p95 |
| Own fast agent TTFV | **~60 min UNVERIFIED estimate**, plausible 45–90 | **≤10 min p50** |
| Commands before demo | clone + cd + sync/run | one `uvx` line |
| Configuration form | Python builder | `arci init` → schema-validated YAML |
| Concepts required before first run | many | baseline, candidate, independent success check, allowed drop |
| First-run interpretation | substantial reading | one-line verdict explanation |

The smallest generated descriptor should be roughly this conceptual surface:

```yaml
experiment_id: checkout-retry
task:
  order_id: order-7

toolset: tests.world:make_world
oracle: tests.world:passed

baseline: app.v1:run
candidate: app.v2:run

conditions:
  - id: reserve-timeout
    fault:
      name: tool_timeout
      tool: reserve
      occurrence: 0

alpha: 0.05
delta: 0.10
n_per_arm: 5   # smoke run; expect INCONCLUSIVE
```

This is **not** a proposal to replace the canonical schema fields. It is the human-facing descriptor translated directly into the existing `Manifest`; defaults and aliases must be deterministic, generated schema-visible, and sealed before scheduling. The existing Python builder remains the advanced/programmable path. ARCI already rejects unknown fields and freezes its Pydantic models, which is the right base for this. fileciteturn14file0

The smallest gateable agent remains the existing plain-function contract—`agent(task, tools, rng) -> dict`—plus an independent world/oracle; command agents remain the second path behind the harness-owned MCP boundary. fileciteturn2file0 A browser route should be additive: put an **Open in Codespaces** link below the first screen with the same packaged quickstart. It should not become the primary installation route because `uvx` is already faster and more portable for a Python CLI.

## Adoption plan

The first ten external users should not be random “AI builders”. They should already have public evidence of the exact problems ARCI addresses.

| Target | Where to find them | Dated evidence of problem | Ask |
|---|---|---|---|
| **Promptfoo maintainers/users around #5947** | `promptfoo/promptfoo` | Repeated-success measurement request opened 16 Oct 2025; implementation work still active into Sep 2026. fileciteturn6file0 | Run one existing stochastic agent change through ARCI rather than debate metrics abstractly. |
| **Inspect AI agent-eval maintainers** | `UKGovernmentBEIS/inspect_ai` ecosystem | 2026 issues around scorer crashes, provider schemas and proving agent completion. citeturn11search14turn11search15turn11search17 | Pilot an Inspect-driven command agent behind ARCI’s MCP boundary. |
| **tau2/tau3 maintainers** | tau benchmark repo/community | Jan 2026 RFC asks for realistic API failures; v1.0.1 later changed grading enough to move some metrics materially. citeturn17search11turn17search0 | Use ARCI-style prospective fault conditions on one task fixture; no benchmark comparison claim. |
| **MCP Inspector maintainers** | `modelcontextprotocol/inspector` | Active v2.10.1 on 8 Oct; September 2026 concurrency/hang reports show real server-testing pain. fileciteturn23file0 citeturn9search9 | Validate Inspector→ARCI two-stage CI recipe. |
| **Pydantic AI testing users** | issue #3138 and Pydantic community | 11 Oct 2025 issue asks for stronger framework-level agent testing despite existing test models. citeturn13search1 | Pilot the Python-function recipe without asking Pydantic AI to change its test layer. |
| **Claude Agent SDK reliability reporters** | `anthropics/claude-agent-sdk-*` issues | Issue #701, 19 Mar 2026: repeatable hangs after tool calls; other March issues concern session JSONL. citeturn15search13turn15search10 | Give ARCI a versioned session fixture and try prospective rerun. |
| **LangSmith OTel users** | `langchain-ai/langsmith-sdk` | June and August 2026 OTel issues expose real interchange/semantic friction. citeturn22search5turn22search15 | Validate `arci import otlp` on a real exported trace. |
| **Phoenix/OpenInference users** | `Arize-ai/phoenix` | April 2026 reports of trace export failing after redeployment despite pinned top-level packages. citeturn22search8turn22search9 | Supply authentic OTLP/OpenInference fixture and test completeness reporting. |
| **agent-chaos maintainer/users** | `deepankarm/agent-chaos` | Active 2026 tool/model fault framework demonstrates direct demand for resilience testing. citeturn10search0 | Align taxonomy and identify one deterministic scenario worth an ARCI custom-fault recipe. |
| **Chronicle maintainers** | `theagentplane/chronicle` | Active through 12 Oct 2026; its explicit purpose is committing production agent failures as replayable regression tests. fileciteturn21file0 | Explore record interop instead of competing replay implementations. |

The three tutorials should be concrete enough that their source tree can double as acceptance tests:

**“Your MCP agent loses one retry.”** Start with a command agent and MCP server. Run Inspector preflight, inject the first `reserve` timeout, compare baseline and candidate, receive the four-way verdict, minimise the fault set and replay the recording. This is the generalised version of ARCI’s strongest existing fixture, not a new showcase. fileciteturn2file0

**“Gate a coding-agent permission hook when the decision service disappears.”** Use the same shape as the already-recorded frontier-scout guardrail run, but package it as a reproducible recipe rather than a claim about native Claude/Codex enforcement. The existing result ran the hook through ARCI’s harness, not inside a native coding-agent session, so the tutorial must retain that limitation. fileciteturn2file0

**“Import a LangGraph/Pydantic/OpenTelemetry session, then preregister the rerun.”** First use `arci import otlp` to locate the observed tool sequence and draft a condition; then explicitly start a *new sealed experiment* for any reliability verdict. This teaches the most important trust distinction: retrospective telemetry helps formulate the test; it does not become prospective evidence.

**First integration partner: MCP Inspector.** It is the cleanest complement because it has >11k-star adoption, a current release five days before this memo, a machine-oriented CLI, and does not compete with ARCI’s statistical gate. fileciteturn15file0 fileciteturn23file0 The proposed upstream PR after v0.8.0 is a small documentation/example change: **“CI: protocol preflight with Inspector, stochastic resilience with ARCI”**. The fixture would run Inspector’s CLI to validate/connect/list/call the MCP tools and then invoke the published ARCI package against a baseline/candidate agent. The text must explicitly say Inspector remains the MCP testing/debugging tool and ARCI adds repeated fault-conditioned regression evidence.

Launch channels should follow the evidence, not precede it:

| Order | Channel | Single claim, backed by a recorded run |
|---|---|---|
| First | **GitHub v0.8.0 release / README** | “Run ARCI’s recorded retry regression without cloning in one `uvx` command.” |
| Second | **Show HN** | “A CI gate for stochastic agent changes that can honestly return INCONCLUSIVE and replay the boundary failure.” |
| Third | **MCP repository/community channels after Inspector recipe** | “Inspector checks the MCP interface; ARCI compares agent behaviour under predeclared MCP tool faults.” |
| Fourth | **Promptfoo / Inspect / Pydantic issue discussions where directly relevant** | “Here is a recorded complementary workflow for repeated reliability; it does not replace your evaluator.” |
| Fifth | **r/LocalLLaMA / agent-builder communities** | “The demo itself makes no model call; local-model experiments can still remain INCONCLUSIVE rather than being rerun until green.” |

Metrics should be recorded in-repo like the existing evidence, with failures kept:

| Metric | Target | By |
|---|---:|---|
| Packaged demo TTFV | p50 ≤2 min; p95 ≤3 min on clean reference machines | **20 Oct 2026** |
| Own fast-agent TTFV | p50 ≤10 min; at least 4/5 cold users ≤15 min | **27 Oct 2026** |
| Cold-read comprehension | ≥80% of readers correctly answer all five questions without maintainer explanation | **12 Nov 2026** |
| First external recorded ARCI run | 1 independent repository | **31 Oct 2026** |
| External recorded runs | ≥5 runs across ≥3 independent repos | **30 Nov 2026** |
| External Action references | ≥5 public repositories referencing a released ARCI Action tag | **15 Dec 2026** |
| First-user cohort | 10 external people/projects attempted onboarding | **11 Jan 2027** |
| Issues from strangers | ≥5 substantive bug/design/onboarding issues, excluding bots/spam | **11 Jan 2027** |

Do not add telemetry to manufacture these metrics. TTFV data can be contributed as small timing receipts; Action adoption can be counted from public workflow references; pilot results can be committed with consent.

Kill criteria belong to features, not ARCI:

| Bet | Kill / convert criterion |
|---|---|
| PyPI/uvx | If reproducible clean installs cannot pass on Ubuntu+macOS by 17 Oct, delay PyPI rather than weakening package integrity; release from GitHub remains fallback. |
| `arci init` | If fewer than 7/10 cold users produce a runnable descriptor without syntax surgery by 12 Nov, replace the interface rather than adding options. |
| YAML/schema | If it cannot round-trip all sprint-supported Manifest semantics without a second source of defaults/validation, keep it as an `init` input template only. |
| Cookbook | If a recipe cannot get a fresh user to a valid verdict under its stated time budget, fix/remove it before adding more recipes. |
| OTLP importer | If authentic fixtures from two independent OTel producers cannot preserve enough tool identity/order to be useful by 12 Nov, keep it experimental and do not promise replay. |
| Claude/Codex importers | If provider formats churn faster than fixtures can be maintained, drop direct parsers and accept only OTLP/hook-normalised input. |
| Broad SDK adapters | **Already killed** by duplication; recipes only. |
| MCP-server gating | If a design cannot compare server versions without weakening the trusted-environment/oracle model by 1 Dec, do not add it to ARCI. |
| HTML/PR comment/badge | No build until ≥3 external users independently ask for richer reporting than Step Summary/artifacts. |
| Windows | If native Windows requires weakening process cleanup, stdio isolation or replay guarantees, remain POSIX-native and document WSL. |
| Per-request pacing | Ship the narrow correctness fix; kill any broader rate-limit scheduler if no demonstrated requirement exists. |
| Counterfactual replay | **Already killed** as a standalone build because Chronicle covers the core wheel. |
| Permission calibration | No labelled external permission dataset + real user by 1 Dec ⇒ push beyond the 90-day plan. |

## Proof of non-duplication, do-not-build list, sources and open questions

For every sprint task, the nearest wheel already exists; the point of the task is the delta.

| Sprint task | Closest existing thing | One-line delta |
|---|---|---|
| S1 packaging | [`uv build` / `uv publish`](https://docs.astral.sh/uv/guides/package/) and PyPI trusted publishing; current 2026 tooling. citeturn11search0 | ARCI uses standard Python distribution; no package manager code. |
| S2 packaged demo | [`uvx`](https://docs.astral.sh/uv/guides/tools/) isolated tool runner. citeturn11search3 | Only package ARCI’s existing fixture so uvx can reach it. |
| S3 YAML/schema | Pydantic Evals serialisation + JSON Schema. citeturn13search0 | Generate schema from ARCI’s existing immutable Manifest rather than creating a configuration framework. |
| S4 `arci init` | `uv init`, Promptfoo init, Playwright init. citeturn20search2turn20search1turn20search5 | Generates an ARCI experiment descriptor only. |
| S5 smoke UX | ARCI’s already-landed `arci plan` and published operating characteristics. fileciteturn6file0 | Makes existing power information unavoidable during onboarding. |
| S6 README | Ruff/uv/Promptfoo/Playwright/k6 quickstarts. citeturn20search0turn19search0 | Documentation ordering only; no new runtime. |
| S7 Python recipe | OpenAI `ScriptedModel`, Pydantic `FunctionModel`/test utilities. citeturn4search0turn13search2 | Shows how those unit-test layers compose with ARCI’s repeated prospective gate. |
| S8 MCP recipe | MCP Inspector v2.10.1. fileciteturn23file0 | Inspector checks/debugs protocol; ARCI measures baseline-vs-candidate behaviour under faults. |
| S9 TTFV harness | Mature quickstarts measure their value through immediate runnable flows; no unique external runtime needed. | Records ARCI onboarding latency; does not become product telemetry. |
| S10 release main features | evalsig / benchmark pass metrics already cover statistical analysis concepts. fileciteturn20file0 citeturn17search1 | S10 does not add new inference; it releases code already on ARCI main. |
| S11 Action/install matrix | Promptfoo Action + standard GitHub Actions. citeturn12search4 | Tests ARCI’s existing composite action; no new CI platform. |
| S12 release | Standard PyPI/GitHub release machinery. | Produces provenance/evidence around existing code; no package registry or updater. |

**Do not build during these 90 days:** a general-purpose evaluation framework; LLM-as-judge/scorer infrastructure; another MCP Inspector/conformance client; an observability backend or trace database; a generic LLM HTTP chaos proxy; a broad fault catalogue; SDK-specific fake models; arbitrary HTTP cassette infrastructure; a new cut-point/counterfactual replay engine; a general statistics package; a sandbox/security product; rich dashboards/badges before user demand; or runtime coupling to actseal, dorian, frontier-scout or any sibling project. The reasoning is respectively Promptfoo/Inspect/DeepEval/Pydantic Evals, MCP Inspector, Langfuse/Phoenix/LangSmith, agent-chaos/AgentChaos, official SDK test utilities, VCR.py, Chronicle, SciPy/evalsig and ARCI’s own declared trust boundary. citeturn10search0turn18search0turn18search1 fileciteturn10file0

Four open questions actually change the plan:

1. **Is an `INCONCLUSIVE` smoke result acceptable as “first verdict” for the ≤10 minute product goal?** This report assumes yes, consistent with ARCI’s stated philosophy. If “first verdict” is intended to mean a decisive PASS/BLOCK, the ten-minute goal is statistically incompatible with many realistic agents and should be changed rather than gamed.
2. **Is the exact PyPI name `agent-reliability-ci` available on 13 October 2026?** **UNVERIFIED** in this research pass. If unavailable, only the distribution name changes; the CLI should remain `arci`.
3. **Does “Windows support” mean native process semantics or is WSL acceptable for the first external Windows users?** Native support has materially more trust-model work.
4. **Which first external native coding-agent campaign should be authoritative: a Claude hook or a Codex hook/session?** Pick one after the first pilot; do not split the sprint across both.

The principal dated sources are:

| Source | Date / checked state | Relevance |
|---|---|---|
| [ARCI README](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/README.md) | main inspected 13 Oct 2026 | Current onboarding, claims, examples and limits. fileciteturn2file0 |
| [ARCI ROADMAP](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/ROADMAP.md) | main inspected 13 Oct 2026 | Existing priorities and unreleased state. fileciteturn3file0 |
| [ARCI statistical contract](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/STATISTICS.md) | main inspected 13 Oct 2026 | Gate semantics, sample-size honesty, sequential looks. fileciteturn9file0 |
| [ARCI trust model](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/TRUST_MODEL.md) | main inspected 13 Oct 2026 | Boundary and non-security limits. fileciteturn10file0 |
| [ARCI evidence report](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/reports/ci-gate-2026-10-06/REPORT.md) | related work checked 5 Oct; report 6 Oct 2026 | Current related work and measured operating characteristics. fileciteturn6file0 |
| [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai) | checked 13 Oct 2026 | Durable GenAI/MCP telemetry seam. citeturn22search4 |
| [MCP Inspector](https://github.com/modelcontextprotocol/inspector) | v2.10.1, 8 Oct 2026 | MCP protocol/debug wheel to reuse. fileciteturn23file0 |
| [Promptfoo](https://github.com/promptfoo/promptfoo) | 0.124.x active 6–8 Oct 2026 | Evaluation/CI incumbent and repeated-success demand. citeturn12search2 |
| [OpenAI Agents SDK testing](https://openai.github.io/openai-agents-python/testing/) | checked Oct 2026 | Existing deterministic SDK-test wheel. citeturn4search0 |
| [Pydantic AI / Evals](https://github.com/pydantic/pydantic-ai) | v2.51.0, 25 Sep 2026 | Config/schema precedent and SDK testing. citeturn12search0turn13search0 |
| [Arize Phoenix](https://github.com/Arize-ai/phoenix) | checked Oct 2026 | OTel/OpenInference observability ecosystem. citeturn22search0 |
| [LangSmith collector proxy](https://github.com/langchain-ai/langsmith-collector-proxy) | checked Oct 2026 | OTLP JSON/protobuf ingestion. citeturn22search6 |
| [Chronicle](https://github.com/theagentplane/chronicle) | active 12 Oct 2026 | Existing decision-graph/cut-point replay. fileciteturn21file0 |
| [agent-chaos](https://github.com/deepankarm/agent-chaos) | checked 2026 | Existing agent/model/tool chaos wheel. citeturn10search0 |
| [On Randomness in Agentic Evals](https://arxiv.org/abs/2602.07150) | rev. 23 Mar 2026 | Repetitions, power, eval variance. citeturn16academia48 |
| [Anthropic infrastructure noise](https://www.anthropic.com/engineering/infrastructure-noise) | 5 Feb 2026 | Resource configuration changes measured agent performance. citeturn16search6 |
| [SciPy 1.18.1](https://github.com/scipy/scipy/releases/tag/v1.18.1) | 21 Aug 2026 | External statistical reference implementation. fileciteturn16file0 |

The non-load-bearing **UNVERIFIED** items in this memo are exact current release/licence metadata for several SDK/platform rows where the relevant feature was verified but release metadata was not; the exact PyPI distribution-name availability; and today’s 60-minute/8-minute TTFV estimates. No development decision depends on an unverified SDK version, licence, star count or TTFV estimate.

## Machine-readable appendix

```yaml
ttfv:
  today_estimate_min: 60
  target_min: 10
  path:
    - "Install from PyPI with: uv tool install agent-reliability-ci"
    - "For the zero-clone demo: uvx --from agent-reliability-ci arci demo"
    - "Scaffold the user's experiment with arci init and four required refs: baseline, candidate, toolset, oracle."
    - "Generate a schema-valid arci.yaml that maps directly to the existing Pydantic Manifest."
    - "Use n_per_arm: 5 only as an explicitly labelled smoke design; an honest INCONCLUSIVE counts as a valid first verdict."
    - "Run arci run arci.yaml."
    - "Use arci plan before sealing a larger confirmatory CI experiment."
    - "Target demo TTFV is <=2 minutes; target own-fast-agent TTFV is <=10 minutes p50."
    - "The 60-minute current estimate is UNVERIFIED and must be replaced by measured cold-user data."

first_screen:
  one_liner: "ARCI runs your baseline and candidate repeatedly under the same predeclared conditions, then returns PASS, BLOCK, INCONCLUSIVE or ERROR and can replay a recorded failure."
  commands:
    - "uvx --from agent-reliability-ci arci demo"
    - "uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml"
  readme_text: |
    **Did this change make your agent less reliable?**

    ARCI runs your baseline and candidate repeatedly under the same predeclared
    conditions, then returns PASS, BLOCK, INCONCLUSIVE or ERROR and can replay
    a recorded failure.

    `uvx --from agent-reliability-ci arci demo`

    `uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed && arci run arci.yaml`

    baseline + candidate -> same frozen tasks/faults -> repeated trials
    -> verdict -> minimise/replay

    PASS means only this: on this predeclared experiment, the candidate was not
    shown to be worse than the baseline by more than the allowed drop. It is
    not a claim of absolute reliability.

    A small first run will often be INCONCLUSIVE. That is a valid result; use
    `arci plan` before choosing a larger confirmatory run.

    ARCI observes calls that cross its tool boundary. It is not a sandbox, it
    does not replay model inference, and trace divergence shows where runs
    differ—not why.

wheel_map:
  - name: "evalsig"
    url: "https://github.com/vtensor/evalsig"
    date: "2026-05-17 last verified push; no release verified"
    overlap: "Power planning, three-way statistical gates, paired/clustered analysis and monitoring."
    action: "compete"
    integration_point: "No runtime dependency; reference as an alternative statistical toolkit."
  - name: "Promptfoo"
    url: "https://github.com/promptfoo/promptfoo"
    date: "0.124.x active in October 2026; repeated-success issue active through 2026"
    overlap: "General LLM evaluation, regression CI, repeated-success metrics."
    action: "integrate"
    integration_point: "Complementary recipe; do not ingest retrospective Promptfoo scores as prospectively registered ARCI evidence."
  - name: "Inspect AI"
    url: "https://github.com/UKGovernmentBEIS/inspect_ai"
    date: "Active 2026; exact current package release UNVERIFIED"
    overlap: "Agent tasks, tools, scorers, logs and sandboxed evaluation."
    action: "integrate"
    integration_point: "Run compatible Inspect-driven agents as ARCI command arms; retain Inspect's own scorer/runtime."
  - name: "DeepEval"
    url: "https://github.com/confident-ai/deepeval"
    date: "4.2.x active in 2026; exact 13 October release UNVERIFIED"
    overlap: "Evaluation cases, metrics and agent evaluation."
    action: "ignore"
    integration_point: "Cookbook interoperability only; no scorer framework in ARCI."
  - name: "Pydantic Evals / Pydantic AI"
    url: "https://github.com/pydantic/pydantic-ai"
    date: "v2.51.0, 2026-09-25"
    overlap: "Evaluators, test models, YAML/JSON serialisation and generated JSON Schema."
    action: "integrate"
    integration_point: "Generate ARCI JSON Schema from the existing Pydantic Manifest; no runtime dependency."
  - name: "OpenAI Agents SDK test utilities"
    url: "https://openai.github.io/openai-agents-python/testing/"
    date: "Official documentation checked 2026-10-13; exact latest SDK release UNVERIFIED"
    overlap: "Deterministic model and orchestration testing."
    action: "integrate"
    integration_point: "Allow official SDK test doubles inside an arm; ARCI owns scheduling, faults and gate."
  - name: "Claude Agent SDK and hooks"
    url: "https://github.com/anthropics/claude-agent-sdk-python"
    date: "0.3.x active late September/October 2026; exact release date UNVERIFIED"
    overlap: "Sessions, lifecycle hooks, tool events."
    action: "integrate"
    integration_point: "Import official hook/session data into the common analysis record; no SDK monkey-patching."
  - name: "Google ADK / Agents CLI"
    url: "https://github.com/google/adk-python"
    date: "Agents CLI evaluation GA in 2026; exact current release UNVERIFIED"
    overlap: "Agent execution, datasets and evaluation."
    action: "integrate"
    integration_point: "Command-agent and OTLP recipes; no duplicate evaluator."
  - name: "Microsoft Agent Framework evaluation"
    url: "https://github.com/microsoft/agent-framework"
    date: "Official evaluation documentation current in 2026; exact current release UNVERIFIED"
    overlap: "Provider-agnostic evaluation abstractions."
    action: "ignore"
    integration_point: "Framework programs can be command arms; keep evaluators separate."
  - name: "OpenTelemetry GenAI semantic conventions and OTLP"
    url: "https://github.com/open-telemetry/semantic-conventions-genai"
    date: "Semantic Conventions 1.44.0 / OTLP 1.11.0 current in October 2026"
    overlap: "Trace/span interchange for GenAI, tools and MCP; no reliability gate."
    action: "integrate"
    integration_point: "arci import otlp; JSON first, protobuf second; imported records are analysis-only."
  - name: "Langfuse"
    url: "https://github.com/langfuse/langfuse"
    date: "v4 current October 2026; legacy ingestion sunset 2026-11-16"
    overlap: "Trace storage, evaluation, experiment comparison and UI."
    action: "integrate"
    integration_point: "OTLP only; no vendor-specific ARCI importer."
  - name: "Arize Phoenix"
    url: "https://github.com/Arize-ai/phoenix"
    date: "Repository checked October 2026"
    overlap: "OTel/OpenInference tracing, experiments, evaluations and replay/playground."
    action: "integrate"
    integration_point: "Consume OTLP/OpenInference via the generic importer."
  - name: "LangSmith OTel"
    url: "https://github.com/langchain-ai/langsmith-collector-proxy"
    date: "OTLP JSON/protobuf support verified in 2026"
    overlap: "Tracing, experiment analysis and storage."
    action: "integrate"
    integration_point: "OTLP only; no LangSmith-specific trace-store dependency."
  - name: "agent-chaos"
    url: "https://github.com/deepankarm/agent-chaos"
    date: "Active 2026; exact current release date UNVERIFIED"
    overlap: "Broad model/tool/user fault injection."
    action: "integrate"
    integration_point: "Use its fault taxonomy as evidence; add mappings only for deterministic ARCI custom faults."
  - name: "MCP Inspector"
    url: "https://github.com/modelcontextprotocol/inspector"
    date: "v2.10.1, 2026-10-08"
    overlap: "MCP testing, debugging, discovery and protocol/conformance workflow."
    action: "integrate"
    integration_point: "Inspector CLI preflight before ARCI repeated fault/reliability runs."
  - name: "Chronicle"
    url: "https://github.com/theagentplane/chronicle"
    date: "Active through 2026-10-12; no tagged latest release verified"
    overlap: "Agent decision recording and cut-point replay."
    action: "integrate"
    integration_point: "Interop spike at ARCI RecordedCall/event level; do not build a competing counterfactual replay engine."
  - name: "VCR.py and pytest-recording"
    url: "https://github.com/kevin1024/vcrpy"
    date: "VCR.py 8.2.1 security-fixed in 2026"
    overlap: "HTTP cassette recording and deterministic replay."
    action: "ignore"
    integration_point: "May be used in adapter tests; never canonical ARCI evidence."
  - name: "Codex App Server / OpenAI session OTLP"
    url: "https://openai.com/index/unlocking-the-codex-harness/"
    date: "App Server architecture 2026-02-04; OTLP session export verified in 2026"
    overlap: "Coding-agent session/event source."
    action: "integrate"
    integration_point: "Prefer OTLP; use App Server JSONL only for missing semantics; do not depend on UNVERIFIED codex --json."
  - name: "SciPy"
    url: "https://github.com/scipy/scipy/releases/tag/v1.18.1"
    date: "v1.18.1, 2026-08-21"
    overlap: "Reference statistical distributions/tests."
    action: "ignore"
    integration_point: "Reference/differential tests only; do not silently replace ARCI's sealed statistical implementation."
  - name: "Randomness guidance and tau2/tau3"
    url: "https://arxiv.org/abs/2602.07150"
    date: "paper revision 2026-03-23; tau2/tau3 v1.0.1 2026-07-22"
    overlap: "Repeated trials, pass^k-style metrics, power and infrastructure-noise guidance."
    action: "integrate"
    integration_point: "Methodology/docs and arci plan; pass^k remains descriptive."

bets:
  - name: "PyPI package and uvx demo"
    scores:
      demand: 5
      non_duplication: 5
      ttfv: 5
      fit: 5
      seven_day_slice: 5
      durability: 4
    decision: "SHIP v0.8.0"
  - name: "arci init"
    scores:
      demand: 5
      non_duplication: 5
      ttfv: 5
      fit: 5
      seven_day_slice: 4
      durability: 5
    decision: "SHIP v0.8.0"
  - name: "Declarative manifest plus JSON Schema"
    scores:
      demand: 4
      non_duplication: 4
      ttfv: 5
      fit: 4
      seven_day_slice: 4
      durability: 5
    decision: "SHIP as thin front-end; Python builder remains escape hatch"
  - name: "Reliability recipes cookbook"
    scores:
      demand: 5
      non_duplication: 5
      ttfv: 5
      fit: 5
      seven_day_slice: 5
      durability: 4
    decision: "SHIP first two in v0.8.0"
  - name: "OTLP GenAI importer"
    scores:
      demand: 5
      non_duplication: 5
      ttfv: 3
      fit: 4
      seven_day_slice: 3
      durability: 5
    decision: "BUILD in 30-day plan, analysis-only first"
  - name: "Claude and Codex session importers"
    scores:
      demand: 4
      non_duplication: 4
      ttfv: 3
      fit: 4
      seven_day_slice: 3
      durability: 3
    decision: "BUILD behind common importer seam"
  - name: "First-class adapters for every major agent SDK"
    scores:
      demand: 4
      non_duplication: 0
      ttfv: 3
      fit: 3
      seven_day_slice: 2
      durability: 2
    decision: "DROP; convert to recipes and trace hooks"
  - name: "Reliability gating for MCP servers"
    scores:
      demand: 4
      non_duplication: 3
      ttfv: 2
      fit: 2
      seven_day_slice: 1
      durability: 5
    decision: "90-day design experiment only"
  - name: "HTML report, PR comment and badge"
    scores:
      demand: 3
      non_duplication: 1
      ttfv: 2
      fit: 4
      seven_day_slice: 4
      durability: 2
    decision: "DROP bundle; existing Step Summary is sufficient until demand"
  - name: "Native Windows support"
    scores:
      demand: 3
      non_duplication: 5
      ttfv: 2
      fit: 3
      seven_day_slice: 2
      durability: 5
    decision: "Conditional 90-day bet"
  - name: "Per-request pacing through parent IPC"
    scores:
      demand: 4
      non_duplication: 5
      ttfv: 1
      fit: 5
      seven_day_slice: 4
      durability: 5
    decision: "HIGH PRIORITY immediately after v0.8.0"
  - name: "Counterfactual replay"
    scores:
      demand: 4
      non_duplication: 0
      ttfv: 1
      fit: 3
      seven_day_slice: 2
      durability: 2
    decision: "DROP implementation; investigate Chronicle interop"
  - name: "Permission-decision calibration"
    scores:
      demand: 2
      non_duplication: 5
      ttfv: 1
      fit: 4
      seven_day_slice: 3
      durability: 3
    decision: "DEFER until labelled external use case exists"

sprint_7d:
  - id: "S1"
    title: "Publishable package pipeline"
    goal: "Publish the already-defined wheel/CLI through standard Python packaging."
    acceptance: "Clean uv tool install works on Python 3.11 and 3.14 without a checkout."
    est_hours: 4
    depends_on: []
    reuses: ["pyproject.toml", "Hatch wheel config", "arci console script"]
    integrates_with: ["PyPI", "uv build", "uv publish"]
  - id: "S2"
    title: "Packaged arci demo"
    goal: "Make the existing recorded retry demonstration runnable without cloning."
    acceptance: "uvx --from agent-reliability-ci arci demo works from an empty directory, makes no model call, exercises gate/diagnosis/replay and finishes <=2 minutes on reference machines."
    est_hours: 5
    depends_on: ["S1"]
    reuses: ["retry-agent example", "gate", "diff", "minimise", "bundle", "replay"]
    integrates_with: ["uvx"]
  - id: "S3"
    title: "Declarative descriptor and generated JSON Schema"
    goal: "Provide a human-editable front-end without creating a second manifest engine."
    acceptance: "Descriptor maps into existing Pydantic Manifest and seals canonical JSON; no decision logic exists in the YAML layer; JSON Schema is generated from code."
    est_hours: 7
    depends_on: []
    reuses: ["arci.schema.Manifest", "Pydantic validation"]
    integrates_with: ["JSON Schema"]
  - id: "S4"
    title: "arci init"
    goal: "Scaffold an own-agent experiment in one command."
    acceptance: "Given experiment name, baseline, candidate, toolset and oracle refs, writes a schema-valid runnable descriptor without syntax hand-editing."
    est_hours: 8
    depends_on: ["S3"]
    reuses: ["Manifest defaults", "descriptor schema"]
    integrates_with: ["uv/Promptfoo/Playwright onboarding pattern"]
  - id: "S5"
    title: "Honest smoke-design UX"
    goal: "Reach a first verdict quickly without presenting a tiny run as confirmatory."
    acceptance: "Generated config uses a small explicitly labelled smoke N; CLI warns that INCONCLUSIVE is expected and points to arci plan; no outcome-dependent extension."
    est_hours: 3
    depends_on: ["S4"]
    reuses: ["arci plan", "existing statistical contract"]
    integrates_with: ["published eval sample-size guidance"]
  - id: "S6"
    title: "README first-screen replacement"
    goal: "Make ARCI understandable in one minute."
    acceptance: "First screen is <=200 words in the prescribed order and keeps relative-PASS and not-a-sandbox limits above the fold."
    est_hours: 4
    depends_on: ["S2", "S4"]
    reuses: ["current recorded hero evidence", "existing figure"]
    integrates_with: ["uv", "Ruff", "Promptfoo", "Playwright", "k6 onboarding patterns"]
  - id: "S7"
    title: "Python-agent reliability recipe"
    goal: "Get a Python agent to a real ARCI verdict with minimal concepts."
    acceptance: "Blank sample project reaches a valid verdict by supplying four project refs plus task data; no gate/statistics code copied."
    est_hours: 3
    depends_on: ["S4"]
    reuses: ["Python agent interface", "retry example"]
    integrates_with: ["framework-native SDK test utilities where useful"]
  - id: "S8"
    title: "MCP command-agent recipe and Inspector preflight"
    goal: "Compose MCP conformance/debugging with ARCI reliability testing."
    acceptance: "Recipe invokes Inspector for MCP preflight and ARCI for repeated fault runs, explicitly distinguishing responsibilities."
    est_hours: 4
    depends_on: ["S4"]
    reuses: ["MCP shim", "MCP boundary", "McpServerSpec"]
    integrates_with: ["MCP Inspector"]
  - id: "S9"
    title: "TTFV and cold-read measurement harness"
    goal: "Replace planning estimates with repeatable measurements."
    acceptance: "Checklist records install, scaffold, run and verdict-interpretation milestones for five cold readers without maintainer coaching."
    est_hours: 3
    depends_on: ["S2", "S4", "S6"]
    reuses: ["examples", "acceptance tests"]
    integrates_with: []
  - id: "S10"
    title: "Release-integrity merge"
    goal: "Ship unreleased main functionality in the sprint release."
    acceptance: "v0.8.0 changelog includes arci plan, opt-in pass^k and portability fixes; evidence/re-derivation checks remain valid."
    est_hours: 4
    depends_on: []
    reuses: ["unreleased main", "archived-decision tests"]
    integrates_with: []
  - id: "S11"
    title: "Install and Action matrix"
    goal: "Verify distribution and the existing GitHub Action."
    acceptance: "Wheel and Action fixtures pass on Ubuntu/macOS; Windows performs install/import/help smoke only and is not advertised as supported execution."
    est_hours: 3
    depends_on: ["S1", "S10"]
    reuses: ["action.yml", "current CI"]
    integrates_with: ["GitHub Actions", "PyPI"]
  - id: "S12"
    title: "v0.8.0 release and evidence receipt"
    goal: "Publish the installable onboarding release."
    acceptance: "Tag, PyPI files, checksums, exact quickstart, recorded fresh-machine demo timing and Action tag are published with existing trust-model limits."
    est_hours: 3
    depends_on: ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11"]
    reuses: ["existing release/evidence practices"]
    integrates_with: ["GitHub Releases", "PyPI"]

plan_30d:
  - id: "D1"
    title: "Parent-IPC per-request pacing"
    goal: "Replace the documented divide-by-k trial-start approximation."
    acceptance: "Concurrent multi-decision tests demonstrate admitted requests obey the declared rate without changing outcome classification."
    est_hours: 10
    depends_on: ["v0.8.0"]
    reuses: ["decision boundary", "parent runner"]
    integrates_with: ["Jev/live provider rate limits"]
  - id: "D2"
    title: "Import-record provenance model"
    goal: "Create a source-neutral immutable analysis record."
    acceptance: "Imported data records source/version/IDs/completeness/raw digest and cannot masquerade as a scheduled ARCI trial."
    est_hours: 6
    depends_on: ["v0.8.0"]
    reuses: ["hashing", "schema primitives", "event representation"]
    integrates_with: ["OTel", "provider session logs"]
  - id: "D3"
    title: "OTLP JSON importer v1"
    goal: "Make OTLP the first durable external trace seam."
    acceptance: "Authentic versioned fixtures from two independent producers map into analysis records with explicit unsupported/incomplete semantics."
    est_hours: 12
    depends_on: ["D2"]
    reuses: ["events", "diff representation"]
    integrates_with: ["OpenTelemetry GenAI", "OTLP JSON"]
  - id: "D4"
    title: "OTLP protobuf path"
    goal: "Support standard binary OTLP after JSON semantics stabilise."
    acceptance: "Equivalent JSON and protobuf fixtures normalise to equivalent ARCI analysis records."
    est_hours: 8
    depends_on: ["D3"]
    reuses: ["OTLP importer"]
    integrates_with: ["OTLP protobuf"]
  - id: "D5"
    title: "Claude analysis importer"
    goal: "Consume official Claude hook/session output without patching the SDK."
    acceptance: "Versioned real-session fixture imports through D2 model; remains analysis-only."
    est_hours: 10
    depends_on: ["D2"]
    reuses: ["common importer model"]
    integrates_with: ["Claude Agent SDK", "Claude Code hooks/session output"]
  - id: "D6"
    title: "Codex analysis importer"
    goal: "Use OpenAI OTLP first and App Server events only where needed."
    acceptance: "Authentic versioned fixture imports; implementation has no dependency on UNVERIFIED codex --json."
    est_hours: 10
    depends_on: ["D2", "D3"]
    reuses: ["common importer model"]
    integrates_with: ["OpenAI session OTLP", "Codex App Server"]
  - id: "D7"
    title: "Third reliability recipe"
    goal: "Show a framework-native bot composed with ARCI rather than adapted into ARCI."
    acceptance: "Tutorial gates a LangGraph or Pydantic-style agent under a transient tool fault while retaining framework-native tests."
    est_hours: 6
    depends_on: ["v0.8.0"]
    reuses: ["Python/command arms"]
    integrates_with: ["LangGraph or Pydantic AI"]
  - id: "D8"
    title: "External pilot round"
    goal: "Collect the first external usability and run evidence."
    acceptance: "Five target users each produce either one complete external run or one written blocker; TTFV records show all maintainer interventions."
    est_hours: 6
    depends_on: ["S9"]
    reuses: ["recipes", "measurement harness"]
    integrates_with: ["target communities"]

roadmap_90d:
  - id: "R1"
    title: "OTLP importer hardening"
    goal: "Validate the common importer across real observability ecosystems."
    acceptance: "Authentic fixtures from Langfuse plus Phoenix or LangSmith are supported with explicit completeness reporting."
    est_hours: 16
    depends_on: ["D3", "D4"]
    reuses: ["common importer"]
    integrates_with: ["Langfuse", "Phoenix", "LangSmith", "OTLP"]
  - id: "R2"
    title: "External evidence cohort"
    goal: "Move ARCI from maintainer-only evidence to independent use."
    acceptance: "At least 10 external onboarding attempts and >=5 external recorded runs across >=3 independent repositories; failed attempts retained."
    est_hours: 16
    depends_on: ["D8"]
    reuses: ["measurement harness", "recipes"]
    integrates_with: ["external users"]
  - id: "R3"
    title: "Chronicle interop spike"
    goal: "Reuse an existing counterfactual/cut-point replay wheel."
    acceptance: "One ARCI boundary trace converts to a Chronicle-compatible record, or a concrete semantic incompatibility is documented; no new ARCI replay mode."
    est_hours: 8
    depends_on: ["D2"]
    reuses: ["RecordedCall", "events"]
    integrates_with: ["Chronicle"]
  - id: "R4"
    title: "MCP-server reliability design record"
    goal: "Test whether server-version reliability belongs inside ARCI."
    acceptance: "Design record plus prototype; public feature only if server comparison preserves trusted-environment and oracle semantics."
    est_hours: 10
    depends_on: ["external MCP pilot"]
    reuses: ["MCP boundary", "gate"]
    integrates_with: ["MCP Inspector"]
  - id: "R5"
    title: "Native Windows decision"
    goal: "Determine whether Windows can meet the same execution/trust guarantees."
    acceptance: "Full support only if timeout, child cleanup, stdio, path sealing and replay invariants pass; otherwise WSL is documented and native support remains off."
    est_hours: 12
    depends_on: ["S11"]
    reuses: ["portability suite"]
    integrates_with: ["Windows", "Python", "uv"]
  - id: "R6"
    title: "Permission calibration decision"
    goal: "Extend calibration only with a real external labelled use case."
    acceptance: "If built, separate preregistered protocol and labelled permission dataset; no inference from intent-routing calibration."
    est_hours: 12
    depends_on: ["external labelled dataset", "external user"]
    reuses: ["Jev calibration framework"]
    integrates_with: ["coding-agent permission decisions"]
  - id: "R7"
    title: "Resume/index evidence gate"
    goal: "Build resumability only after demonstrated expensive interruption."
    acceptance: "Triggered only after two independent real interruption cases; SQLite indexes but does not replace sealed JSON evidence."
    est_hours: 12
    depends_on: ["two documented interruption cases"]
    reuses: ["existing run stores"]
    integrates_with: ["SQLite"]
  - id: "R8"
    title: "Reporting decision"
    goal: "Avoid UI work before external demand."
    acceptance: "HTML/PR-comment work starts only after three independent external requests; canonical evidence remains machine-readable/Markdown records."
    est_hours: 8
    depends_on: ["R2"]
    reuses: ["Markdown reports", "GitHub Step Summary"]
    integrates_with: ["GitHub"]

adoption:
  first_users:
    - "Promptfoo maintainers/users around repeated-success issue #5947."
    - "Inspect AI maintainers/users working on agent completion and runtime reliability."
    - "tau2/tau3 maintainers interested in realistic API failure modes."
    - "MCP Inspector maintainers and MCP server authors."
    - "Pydantic AI users asking for stronger agent-testing utilities."
    - "Claude Agent SDK users reporting hangs/session-log reliability problems."
    - "LangSmith users working with OTel-ingested spans."
    - "Phoenix/OpenInference users debugging OTLP trace pipelines."
    - "agent-chaos maintainer/users."
    - "Chronicle maintainers/users building committed agent regression tests."
  tutorials:
    - "Your MCP agent loses one retry: Inspector preflight -> ARCI timeout injection -> verdict -> minimise -> replay."
    - "Gate a coding-agent permission hook when its decision service disappears, preserving the existing limitation that the hook is tested through the harness rather than claiming native enforcement."
    - "Import a LangGraph/Pydantic/OpenTelemetry session, use it to formulate a fault condition, then seal and run a new prospective ARCI experiment."
  partner: "MCP Inspector: after v0.8.0, propose a docs/example PR named 'CI: protocol preflight with Inspector, stochastic resilience with ARCI'; Inspector remains the MCP debugger/conformance layer."
  channels:
    - "GitHub v0.8.0 release/README — claim: one-command zero-clone recorded demo."
    - "Show HN — claim: a stochastic agent CI gate that can honestly return INCONCLUSIVE and replay a recorded boundary failure."
    - "MCP community/repository — claim: Inspector validates the MCP interface; ARCI measures agent behaviour under predeclared MCP faults."
    - "Relevant Promptfoo/Inspect/Pydantic issue discussions — claim: complementary prospective reliability workflow, not evaluator replacement."
    - "Local/agent-builder communities — claim: demo makes no model call and local-model experiments are reported honestly even when INCONCLUSIVE."
  metrics:
    - name: "Packaged demo TTFV"
      target: "p50 <=2 min and p95 <=3 min on clean reference machines"
      by: "2026-10-20"
    - name: "Own fast-agent TTFV"
      target: "p50 <=10 min and at least 4/5 cold users <=15 min"
      by: "2026-10-27"
    - name: "Cold-read comprehension"
      target: ">=80% answer all five comprehension questions correctly without maintainer explanation"
      by: "2026-11-12"
    - name: "First external recorded run"
      target: "1 independent repository"
      by: "2026-10-31"
    - name: "External recorded runs"
      target: ">=5 runs across >=3 independent repositories"
      by: "2026-11-30"
    - name: "External Action references"
      target: ">=5 public repositories referencing a released ARCI Action tag"
      by: "2026-12-15"
    - name: "First-user cohort"
      target: "10 external people/projects attempted onboarding"
      by: "2027-01-11"
    - name: "Issues from strangers"
      target: ">=5 substantive bug/design/onboarding issues excluding bots and spam"
      by: "2027-01-11"
  kill_criteria:
    - "PyPI/uvx: if reproducible clean installs fail on Ubuntu+macOS by 2026-10-17, defer PyPI rather than weaken packaging integrity."
    - "arci init: if fewer than 7/10 cold users produce a runnable descriptor without syntax surgery by 2026-11-12, replace the interface."
    - "Declarative manifest: if full supported semantics cannot round-trip without a second source of defaults/validation, keep it only as an init template."
    - "Cookbook: remove or rewrite any recipe that cannot meet its stated fresh-user verdict budget."
    - "OTLP importer: if two independent authentic producer fixtures cannot yield useful ordered tool data by 2026-11-12, keep it experimental and make no replay promise."
    - "Claude/Codex importers: if provider formats churn materially, drop direct parsers and accept OTLP/hook-normalised input only."
    - "Broad SDK adapters: already killed by duplication."
    - "MCP-server gating: if it cannot preserve trusted-environment/oracle semantics by 2026-12-01, do not add it."
    - "HTML/PR comment/badge: do not build until at least three independent external users request richer reporting."
    - "Windows: if native support weakens process cleanup, stdio isolation or replay guarantees, remain POSIX-native and document WSL."
    - "Per-request pacing: ship the narrow correctness fix; kill a broader scheduler absent a demonstrated requirement."
    - "Counterfactual replay: already killed as standalone implementation; use Chronicle interop."
    - "Permission calibration: no labelled external permission dataset and real user by 2026-12-01 means defer beyond the 90-day roadmap."

do_not_build:
  - "A general-purpose LLM/agent evaluation framework."
  - "LLM-as-judge/scorer infrastructure."
  - "Another MCP Inspector/conformance client."
  - "An observability backend or trace database."
  - "A broad LLM HTTP chaos proxy or generic fault catalogue."
  - "First-party fake/test models for every agent SDK."
  - "Generic HTTP cassette infrastructure."
  - "A competing cut-point/counterfactual replay engine."
  - "A general statistics library."
  - "Benchmark superiority claims without matched preregistered experiments."
  - "A sandbox or security-boundary claim."
  - "Rich HTML/PR-bot/badge infrastructure before demonstrated external demand."
  - "Runtime coupling to actseal, dorian, frontier-scout or other sibling projects."

open_questions:
  - "Does the <=10-minute 'first verdict' target explicitly accept INCONCLUSIVE? This plan assumes yes; requiring a decisive PASS/BLOCK would change the product target and sample-size strategy."
  - "Is the exact PyPI distribution name 'agent-reliability-ci' available? UNVERIFIED; only the distribution name changes if not."
  - "For Windows users, is WSL acceptable or is native execution a requirement? Native semantics materially affect the trust-model work."
  - "Which first native coding-agent pilot should be authoritative after OTLP: Claude hooks or Codex/OpenAI session telemetry? Pick one rather than splitting implementation."
```