"""Tutorial Conformer module boundary.

Host conforming and screen matching are components of this module. The current
repository carries their benchmark contract; the production conformer is not
yet implemented.
"""

from __future__ import annotations

from typing import Any


STATUS = "benchmark_components"
REQUIRED_SUMMARY_KEYS = {"case_id", "retrieval", "state_contrasts", "host_audit", "agent_usage"}


def validate_benchmark_summary(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["benchmark summary must be a JSON object"]
    errors = [f"missing required field: {key}" for key in sorted(REQUIRED_SUMMARY_KEYS - set(value))]
    retrieval = value.get("retrieval")
    if retrieval is not None and not isinstance(retrieval, dict):
        errors.append("retrieval must be an object")
    agent_usage = value.get("agent_usage")
    if agent_usage is not None and not isinstance(agent_usage, dict):
        errors.append("agent_usage must be an object")
    return errors


__all__ = ["STATUS", "validate_benchmark_summary"]
