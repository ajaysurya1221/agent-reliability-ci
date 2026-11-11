I maintain ARCI, an open-source regression gate for agents. v2.0 adds a LangChain adapter: you give it your tools and your create_agent settings, and it runs baseline and candidate on the same tasks while injecting tool timeouts, errors and empty results. You fix the tasks and the decision rule before the run; the verdict is PASS, BLOCK, INCONCLUSIVE or ERROR.

The adapter file for the example is about 50 lines: your tools, two settings functions, one make_adapter call.

I pre-registered one comparison and wrote my prediction first: can a 4B local model replace a 12B one on a 24-task order-desk suite? I predicted PASS.

**Result:**

* Trials passed: 12B model 96 of 96, 4B model 70 of 96.
* Injected fault actually fired, per faulted condition: 12B model 24 of 24, 4B model 18 to 20 of 24.

BLOCK after one round, 18 minutes on a laptop with Ollama, no API key. 23 of the 26 failures were one behaviour: the small model called the stock tool with a product code the order did not have. The second line is the part I did not expect: the small model sometimes skipped the lookup, so the injected fault never fired for it. Without counting that, the faulted conditions would have looked like a fair comparison.

What it rejects today, loudly rather than silently: async agents, interrupts, tools with injected arguments, tool artifacts. Which of those matters most to you?

Limits: the result is for the registered suite only, and it is one run of 96 pairs.

Repo: https://github.com/ajaysurya1221/agent-reliability-ci

Result and pre-registration: https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2/phase0/plan/exec/v2/study/RESULT.md

To try it: pip install "agent-reliability-ci[langchain]" then arci init --langchain then arci run arci.yaml
