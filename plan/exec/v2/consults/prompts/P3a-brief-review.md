You are a read-only technical consultant. Change no file and no git state. No network.

Review, before any implementation starts, the brief for ARCI's LangChain adapter:
- plan/exec/v2/tasks/P3a-langchain-adapter-core.md  (the brief under review)
- plan/exec/v2/reviews/S2b-review.md and S2b-review-workflow.json  (binding requirements and findings)
- plan/exec/v2/adr-0012-draft.md and plan/exec/v2/adr-0011-draft.md item 10  (accepted)
- plan/exec/v2/spikes/s2b/  (the phase 0 prototype and FINDINGS.md)
- ARCI code: src/arci/interfaces.py, src/arci/toolbox.py, src/arci/worker.py, src/arci/replay.py
- the installed framework source, which is the authority on LangChain behaviour:
  /Users/ajay/Developer/.arci-worktrees/wt-v2-adapter/.venv/lib/python3.13/site-packages/
  (langchain 1.4.9, langchain_core 1.7.7, langgraph 1.2.20, langgraph-prebuilt 1.1.1)

The brief replaces the prototype's two-middleware splice with: an ARCI-owned wrapper round
create_agent that supplies proxy tools and puts one ARCI middleware first. Check it against
the installed source, reading the code rather than recalling it:
1. Is every mechanism the brief relies on available through public names in these versions?
   (create_agent arguments; AgentMiddleware hooks wrap_tool_call and wrap_model_call and
   their nesting order relative to list position; ToolCallRequest.override; how a
   BaseException raised inside a tool body or middleware travels through the tool node, its
   thread pool and graph.invoke; where structured_response appears; how to detect tools
   that need injected state, store or runtime; the public fake chat models.)
2. Does any requirement in the brief contradict the installed behaviour or another
   requirement? In particular: serial order with retries when the first middleware is
   ARCI's; real tool failures reaching user middleware as the original exception object
   through ToolBox.call (toolbox.py:298-307 normalises them); budget exhaustion being
   uncatchable; detection of a builder that ignores the factory; the infrastructure-error
   classification and whether fail_harness before propagation is sound with the worker's
   latch handling (worker.py:147-199).
3. Is the snapshot contract enough for a user's check function, and is anything in the
   user-facing API wrong or needlessly complex? Name the simpler form.
4. Is each required test achievable offline with these versions?
5. What is missing that will surprise the implementer in the first hour?

Output, under 90 lines: a verdict line `P3a BRIEF: ACCEPT` or `P3a BRIEF: REVISE`; then
blocking findings (each: where, what is wrong, evidence as file:line in the installed
source or ARCI, the exact fix); then non-blocking findings. Label each finding KNOWN,
CODE (read from source) or OPINION. Do not restate the brief.
