"""MCP completion — argument value suggestions for prompts.

Implements the data side of ``completion/complete``: given a reference to a
prompt (or resource template) and a partially-typed argument, return matching
suggestions. Only arguments with an enumerable value set are completed (e.g.
the ``style`` argument of the ``suggest_edits`` prompt); everything else
returns no suggestions, which is a valid empty completion.
"""
from __future__ import annotations

from typing import Any

_MAX_VALUES = 100

# (prompt name, argument name) -> candidate values.
_ENUM_ARGUMENTS: dict[tuple[str, str], list[str]] = {
    ("suggest_edits", "style"): [
        "general", "portrait", "landscape", "product", "street", "food", "macro",
    ],
    ("analyze_composition", "focus"): [
        "all", "framing", "balance", "subject", "leading_lines",
    ],
}


def complete(ref: Any, argument: Any) -> dict[str, Any]:
    """Return a completion result for *argument* under *ref*."""
    values: list[str] = []
    if (isinstance(ref, dict) and ref.get("type") == "ref/prompt"
            and isinstance(argument, dict)):
        candidates = _ENUM_ARGUMENTS.get((str(ref.get("name")), str(argument.get("name"))))
        if candidates:
            prefix = str(argument.get("value", "")).lower()
            values = [c for c in candidates if c.startswith(prefix)]
    return {"completion": {
        "values": values[:_MAX_VALUES],
        "total": len(values),
        "hasMore": len(values) > _MAX_VALUES,
    }}
