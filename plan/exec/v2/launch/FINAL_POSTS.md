# Final launch text, ready to paste (2026-11-12)

Study link used below (a permanent commit link, renders on GitHub):
https://github.com/ajaysurya1221/agent-reliability-ci/blob/333bece48c5a19b86a870623d5520f61aca69565/plan/exec/v2/study/RESULT.md

## Hacker News

- **Title:** `Show HN: ARCI – a pre-registered regression gate for LangChain agents`
- **URL:** `https://github.com/ajaysurya1221/agent-reliability-ci`
- **Text:**

```
I built ARCI because "the agent eval passed" kept meaning "it passed this time". ARCI treats an agent change like a trial: you fix the tasks, the faults to inject and the decision rule before anything runs, and the rule is hashed into every trial so it cannot be adjusted afterwards.

What v2 adds:

- A LangChain adapter. You give it your tools and your create_agent settings; it runs your agent behind a recorded tool boundary and injects tool timeouts, errors and empty results.

- A multi-task gate. Baseline and candidate run the same task-and-fault grid in rounds. The verdict is PASS, BLOCK, INCONCLUSIVE or ERROR, with a proved 2.5% bound on each wrong direction under stated assumptions. INCONCLUSIVE is a real answer, not a failure.

- A single-file HTML report, including how often each injected fault actually fired.

To check it does something, I pre-registered one comparison on my laptop and wrote my prediction down first: could a 4B local model replace a 12B one on a 24-task order-desk suite under four fault conditions? I predicted PASS. It was BLOCK after one round: 96 of 96 against 70 of 96. The report showed why: one task type, where the small model calls a tool with a product code the order does not have. It also showed the injected fault fired in 24 of 24 trials for one model and 18 to 20 of 24 for the other, because the smaller model sometimes skipped the lookup entirely. 18 minutes, no API key, no spend.

Result and pre-registration: https://github.com/ajaysurya1221/agent-reliability-ci/blob/333bece48c5a19b86a870623d5520f61aca69565/plan/exec/v2/study/RESULT.md

Limits, plainly: the guarantee is for the suite you registered, not for other tasks. A PASS is about the suite average and can hide one bad task; the per-task table sits beside the verdict for that reason. Nothing can PASS before about 80 paired runs at the default margin. Synchronous LangChain agents only for now. The study is one run of 96 pairs.

  pip install 'agent-reliability-ci[langchain]'
  arci init --langchain && arci run arci.yaml

I'm one person working with AI coding agents; the design records and every review are in the repo. I'd like to hear where the assumptions break for your agents.
```

## r/LangChain

- **Title:** `I put create_agent behind a fault-injecting regression gate, pre-registered a test, and my own prediction lost`
- **Body:**

```
I maintain ARCI, an open-source regression gate for agents. v2.0 adds a LangChain adapter: you give it your tools and your `create_agent` settings, and it runs baseline and candidate on the same tasks while injecting tool timeouts, errors and empty results. You fix the tasks and the decision rule before the run; the verdict is PASS, BLOCK, INCONCLUSIVE or ERROR.

The adapter file for the example is about 50 lines: your tools, two settings functions, one `make_adapter` call.

I pre-registered one comparison and wrote my prediction first: can a 4B local model replace a 12B one on a 24-task order-desk suite? I predicted PASS.

| | 12B model | 4B model |
|---|---|---|
| Trials passed | 96 of 96 | 70 of 96 |
| Injected fault actually fired (per faulted condition) | 24 of 24 | 18 to 20 of 24 |

BLOCK after one round, 18 minutes on a laptop with Ollama, no API key. 23 of the 26 failures were one behaviour: the small model called the stock tool with a product code the order did not have. The second row is the part I did not expect: the small model sometimes skipped the lookup, so the injected fault never fired for it. Without counting that, the faulted conditions would have looked like a fair comparison.

What it rejects today, loudly rather than silently: async agents, interrupts, tools with injected arguments, tool artifacts. Which of those matters most to you?

Limits: the result is for the registered suite only, and it is one run of 96 pairs.

Repo: https://github.com/ajaysurya1221/agent-reliability-ci
Result and pre-registration: https://github.com/ajaysurya1221/agent-reliability-ci/blob/333bece48c5a19b86a870623d5520f61aca69565/plan/exec/v2/study/RESULT.md

    pip install 'agent-reliability-ci[langchain]'
    arci init --langchain && arci run arci.yaml
```

## GitHub release page

Text: `plan/exec/v2/release/RELEASE_NOTES.md`. Create it at
https://github.com/ajaysurya1221/agent-reliability-ci/releases/new?tag=v2.0.0
