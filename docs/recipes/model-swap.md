# Swap the model

You changed the model; did the agent get worse on your tasks?
The LangChain quickstart compares two models with the same tools and grading rules.
Use version 2.1.0 or newer for the model-swap behavior below.

## Register before running

In an empty project directory, with your provider integration and credentials ready:

```sh
pip install 'agent-reliability-ci[langchain]'
arci init --langchain
export ARCI_QUICKSTART_BASELINE='ollama:baseline'
export ARCI_QUICKSTART_CANDIDATE='ollama:candidate'
python register.py
arci run arci.yaml
arci report RUN_DIR
```

Replace the example model ids with available tool-capable models, and install that
provider's LangChain package first (for `ollama:` ids, `pip install langchain-ollama`). Replace `RUN_DIR` with
the store path printed by `arci run`. Replace the example tasks, tools and checker together
to test your own work; set budgets before registration. Never extend a run to seek PASS.

Different real ids keep one tool retry in both arms, with the same middleware, system
prompt and temperature. The exception is `reasoning=False`, passed only for Ollama ids;
other providers keep their default reasoning policy. Equal real ids compare the retry
change: baseline retries once, candidate has no retry. With both variables unset, both ids
are `offline:scripted` and the same retry-change demo runs offline.

Registration writes each model id as its arm label for a swap, or `retry` / `no-retry`
for equal ids. Labels accept the full ids unchanged and enter the sealed run identity.
Environment settings that disagree with registration are refused; register a new experiment.

## Read the verdict

- **PASS:** evidence of non-inferiority within the registered margin, not absolute reliability.
- **BLOCK:** evidence of regression beyond the margin, or a candidate hard-invariant violation.
- **INCONCLUSIVE:** insufficient evidence either way; CI remains non-green.

Statistical verdicts are given only at the end of complete rounds; the quickstart's first
look is at 96 pairs. With every pair tied, a PASS needs 79 pairs at the defaults;
pairs in the candidate's favour can cross sooner. See [suite statistics](../STATISTICS_SUITE.md).

## Do your tools raise or return their errors?

In the [public order-desk study](../results/order-desk-study.md), a tool raising `ValueError`
ended the trial without showing the error to the model. The candidate passed 70 of 96
trials without the error returned and 428 of 480 with it returned. Those runs used different
rounds and seeds: these are two observations, not a measured effect of returning errors.

Optionally add this middleware to **both** arms' `middleware` lists. It is not part of the
template by default. The adapter places user middleware between its outer and inner
middleware: the model sees the returned error on its next turn, and the failed tool
attempt remains recorded at the boundary.

```python
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage


class ReturnToolErrors(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        try:
            return handler(request)
        except ValueError as exc:
            call = request.tool_call
            return ToolMessage(
                content=f"Error: {exc}", tool_call_id=call["id"], name=call["name"], status="error"
            )
```

This answers a question about one suite and your tasks only. A model-swap verdict says
nothing about other tasks. See the [LangChain recipe](langchain.md) for adapter limits.
