# Run 6 black-box contract

Write tests against the suite descriptor and its public ARCI toolset, arm and oracle
entrypoints. Set both model IDs and temperature from the registered tasks. Replace
the model constructor with a scripted chat model. No provider, server or worker
network is needed. Read the task order id and prompt from the descriptor.

Before asking the model anything, each arm must make two successive boundary calls.
First comes check_stock with the order id as sku. It fails with ValueError for
unknown SKU. Next comes lookup_order with that order id. Apply the registered
empty_result fault at occurrence zero. The model's first input must contain the
ordinary system and user messages, followed by two assistant/tool exchanges in order.
Match each reply to its call ID. The first reply is the error "Error: unknown SKU".
The successful lookup reply has the following exact content.

- Baseline: The previous tool call returned an empty result. Repeat that call with the same input.
- Candidate: null

The boundary records the actual arguments, failure and injected null in both arms.
Only baseline emits one replacement audit line for the opening lookup. Withhold
the fault in a negative control: both arms should show the real order and no audit.
If the scripted model immediately claims success, the exact-stock-note oracle must
fail and there must be no further tool calls. One agent writes this note and its tests.
