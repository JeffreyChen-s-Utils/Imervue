"""Ordered cross-folder photo choices survive presentation filters and workflow steps."""
from __future__ import annotations

from collections.abc import Iterable

STATES = frozenset({"unflagged", "pick", "reject"})


class PhotoWorkflow:
    """Keep one explicit selection; filtering never silently changes bulk targets."""

    def __init__(self):
        self.paths: tuple[str, ...] = ()
        self.selected: set[str] = set()
        self.states: dict[str, str] = {}
        self.filter = "all"
        self.develop_preset = ""
        self.export_preset = ""

    def add(self, paths: Iterable[str], states: dict[str, str] | None = None) -> None:
        """Append unique sources, retaining prior choices and excluding already rejected photos."""
        states = states or {}
        new = tuple(dict.fromkeys(str(path) for path in paths if str(path)))
        existing = set(self.paths)
        additions = tuple(path for path in new if path not in existing)
        if any(states.get(path, "unflagged") not in STATES for path in additions):
            raise ValueError("invalid cull state")
        self.paths += additions
        for path in additions:
            state = states.get(path, "unflagged")
            self.states[path] = state
            if state != "reject":
                self.selected.add(path)

    def choose(self, path: str, selected: bool) -> None:
        """Set an explicit bulk choice; rejected photos must be unflagged/picked first."""
        if path not in self.states:
            raise KeyError(path)
        if selected and self.states[path] != "reject":
            self.selected.add(path)
        else:
            self.selected.discard(path)

    def mark(self, paths: Iterable[str], state: str) -> None:
        """Picking includes a photo; rejecting excludes it without deleting the source."""
        if state not in STATES:
            raise ValueError(f"invalid cull state: {state}")
        targets = tuple(paths)
        if any(path not in self.states for path in targets):
            raise KeyError("photo outside workflow")
        for path in targets:
            self.states[path] = state
            if state == "pick":
                self.selected.add(path)
            elif state == "reject":
                self.selected.discard(path)

    def set_filter(self, state: str) -> None:
        """Change only the displayed subset, including an empty subset."""
        if state != "all" and state not in STATES:
            raise ValueError(f"invalid filter: {state}")
        self.filter = state

    def visible_paths(self) -> tuple[str, ...]:
        """Return the presentation subset in original search/cohort order."""
        return tuple(path for path in self.paths
                     if self.filter == "all" or self.states[path] == self.filter)

    def targets(self) -> tuple[str, ...]:
        """Return all checked non-rejected sources, including choices hidden by a filter."""
        return tuple(path for path in self.paths
                     if path in self.selected and self.states[path] != "reject")
