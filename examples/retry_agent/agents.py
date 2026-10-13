"""Baseline, retry regression and repaired inventory agents.

The implementation lives in :mod:`arci.demo.agents` so that ``arci demo`` runs from an
installed wheel; this module re-exports it, so ``examples.retry_agent.agents:agent_b``
and ``arci.demo.agents:agent_b`` resolve to the same function.
"""

from __future__ import annotations

from arci.demo.agents import Task, agent_a, agent_b, agent_c

__all__ = ["Task", "agent_a", "agent_b", "agent_c"]
