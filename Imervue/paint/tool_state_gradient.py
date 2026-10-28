"""Update gradient fields in their observable mutation order."""
from __future__ import annotations

from Imervue.paint.tool_state_settings import EVENT_GRADIENT, validate_choice


class GradientStateMixin:
    """Update gradient fields in their observable mutation order."""

    def set_gradient(self, *, kind: str | None = None,
                     reverse: bool | None = None,
                     repeat: int | None = None,
                     name: str | None = None) -> bool:
        """Update gradient kind / reverse / repeat / colours. True if anything changed.

        *name* picks a saved multi-stop gradient by name; ``""`` goes back to
        foreground → background.
        """
        from Imervue.paint.gradient import GRADIENT_KINDS
        changes = []
        if kind is not None:
            validate_choice(kind, GRADIENT_KINDS, "gradient kind")
            changes.append(self._set_value("gradient_kind", kind))
        if reverse is not None:
            changes.append(self._set_converted("gradient_reverse", reverse, bool))
        if repeat is not None:
            changes.append(self._set_value("gradient_repeat", max(1, int(repeat))))
        if name is not None:
            changes.append(self._set_converted("gradient_name", name, str))
        changed = any(changes)
        if changed:
            self._publish(EVENT_GRADIENT)
        return changed
