"""Manage named preset buckets and apply snapshots in event order."""
from __future__ import annotations

from Imervue.paint.tool_state_settings import (
    validate_choice, TOOLS, SubTool, EVENT_SUB_TOOL, EVENT_BRUSH, EVENT_FILL,
)


class SubToolStateMixin:
    """Manage named preset buckets and apply snapshots in event order."""

    def add_sub_tool(self, tool: str, name: str) -> SubTool:
        """Capture the current brush + fill settings as a named sub-tool.

        The sub-tool is filed under ``tool`` (one of :data:`TOOLS`).
        An existing sub-tool with the same name on the same tool is
        replaced; the order of other entries is preserved. Returns
        the freshly-stored :class:`SubTool` so callers can inspect it.
        """
        validate_choice(tool, TOOLS, "tool")
        sub_tool = SubTool(name=name, brush=self.brush, fill=self.fill)
        bucket = self.sub_tools.setdefault(tool, [])
        for i, existing in enumerate(bucket):
            if existing.name == sub_tool.name:
                bucket[i] = sub_tool
                break
        else:
            bucket.append(sub_tool)
        self._publish(EVENT_SUB_TOOL)
        return sub_tool

    def remove_sub_tool(self, tool: str, name: str) -> bool:
        """Drop a saved sub-tool. Returns ``True`` if it existed."""
        validate_choice(tool, TOOLS, "tool")
        bucket = self.sub_tools.get(tool)
        if not bucket:
            return False
        for i, existing in enumerate(bucket):
            if existing.name == name:
                del bucket[i]
                if not bucket:
                    del self.sub_tools[tool]
                self._publish(EVENT_SUB_TOOL)
                return True
        return False

    def apply_sub_tool(self, tool: str, name: str) -> bool:
        """Switch to ``tool`` and apply the named sub-tool's settings.

        Returns ``True`` if the preset was found and applied. The full
        brush and fill snapshots replace the live settings; main-tool
        switch happens before the slot writes so listeners see a
        coherent ordering of (tool change → settings change) events.
        """
        validate_choice(tool, TOOLS, "tool")
        bucket = self.sub_tools.get(tool, ())
        for entry in bucket:
            if entry.name == name:
                self.set_tool(tool)
                self.brush = entry.brush
                self.fill = entry.fill
                self._publish(EVENT_BRUSH, EVENT_FILL)
                return True
        return False

    def list_sub_tools(self, tool: str) -> list[SubTool]:
        """Return a fresh list of sub-tools registered under ``tool``."""
        validate_choice(tool, TOOLS, "tool")
        return list(self.sub_tools.get(tool, ()))
