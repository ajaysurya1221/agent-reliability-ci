- **Added:** tool outcomes in suite reports (Markdown, HTML and the JSON key `tool_outcomes`). Per arm: how many trials had a recorded tool failure without an injection marker, and how many of those passed. Per tool: trials with and without a recorded start. Descriptive only; the record does not show why a call failed.
- **Fixed:** the LangChain quickstart, run with two different model ids, also removed the candidate's retry, so a model comparison mixed two changes. Different ids now keep the same retry, prompt and temperature in both arms, and registration labels the arms with the model ids. Equal ids and the offline demo are unchanged. Recipe: [model swap](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.1.0/docs/recipes/model-swap.md).
- **Corrected:** the README said nothing can PASS before about 80 paired runs. That is the figure when every pair is a tie (79 at the defaults); pairs in the candidate's favour cross sooner.
- **Docs:** [both pre-registered runs of the example on two local models](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.1.0/docs/results/order-desk-study.md), with the correction to run 1's first write-up that a reader prompted. New README first screen and a "Related tools" section. Design record [0014](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.1.0/docs/design/0014-v2.1.0-release.md).
- **Unchanged:** every stored record, v1 (`arci/0.5`) report output (the HTML footer shows the new version), the statistics.

**Install:** `pip install agent-reliability-ci==2.1.0`. For the LangChain adapter: `pip install 'agent-reliability-ci[langchain]==2.1.0'`.

Thanks to u/Significant_Tune9219 and u/ChemicalExcellent463 on r/LangChain, whose comments led to the second run and to the tool-outcomes table.
