# Adapter environments (recorded 2026-11-11)

Resolved by the orchestrator from the package index with `uv pip compile`, Python 3.13.

| Environment | langchain | langchain-core | langgraph | langgraph-prebuilt |
|---|---|---|---|---|
| Low (lowest the 1.4.9 metadata allows, other packages at locked versions) | 1.4.9 | 1.7.5 | 1.2.12 | 1.1.0 |
| Lane B, as phase 0 (`lane-b-freeze.txt`) | 1.4.9 | 1.7.7 | 1.2.20 | 1.1.1 |
| Latest inside `>=1.4.9,<2` on this date | 1.4.10 | 1.7.7 | 1.2.20 | 1.1.1 |

- Installing LangChain 1.4.9 into the locked ARCI environment added 25 packages and moved
  none of the existing ones (pydantic stays 2.13.5).
- Python 3.14: the set resolves. Installation on 3.14 has not been tested yet.
- This answers ADR 0012's carried item (the exact Low set). `constraints/adapters-low.txt`
  is written from the first row at integration.
