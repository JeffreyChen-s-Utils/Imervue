"""Pure helper for picking a random motion out of a named group.

The Idle-motion cycler, the drag / land motion hook in the desktop
pet, and any future "event triggers a motion" feature all want the
same selection logic:

1. Filter ``document.motions`` to the requested ``group``.
2. When more than one candidate exists, avoid back-to-back replay
   by excluding the previously picked motion's name.
3. Use cryptographic-grade randomness for the pick so a long-running
   pet doesn't fall into a predictable cycle.

Keeping this here (pure, no Qt, no global state) lets callers unit-
test the policy directly and means the same rule applies in every
caller. The :class:`IdleMotionCycler` was the original home — this
module factors that logic out so it isn't copy-pasted elsewhere.
"""
from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.puppet.document import Motion, PuppetDocument


def pick_random_motion_in_group(
    document: PuppetDocument | None,
    group: str,
    *,
    exclude_name: str | None = None,
) -> Motion | None:
    """Return a random :class:`Motion` whose ``group`` matches.

    ``exclude_name`` lets the caller avoid replaying the previous
    pick when alternatives exist; if every candidate matches the
    exclusion, the rule is dropped (single-motion groups still play
    so the feature isn't silently dead). ``None`` is returned when
    the document has no motions in the group, so callers can use
    the return value as the "did anything happen" signal.
    """
    if document is None:
        return None
    candidates = [m for m in document.motions if m.group == group]
    if not candidates:
        return None
    if len(candidates) > 1 and exclude_name is not None:
        filtered = [m for m in candidates if m.name != exclude_name]
        if filtered:
            candidates = filtered
    if len(candidates) == 1:
        return candidates[0]
    return secrets.choice(candidates)
