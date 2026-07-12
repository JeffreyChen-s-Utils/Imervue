"""Pure routing for Left/Right arrows on the Modify / Paint main tabs.

By default the top-level ``QTabWidget``'s tab bar eats Left/Right to change the
current tab. On the Modify (index 1) and Paint (index 2) tabs the user expects
those arrows to page through images, exactly like the DeepZoom browse view.

The decision — *which* tab, *which* direction, or *ignore* — is kept here as a
Qt-free function so it is unit-testable without building the heavy, GL-backed
main window. The window's ``eventFilter`` is a thin adapter over
:func:`tab_arrow_action`.
"""
from __future__ import annotations

MODIFY_TAB_INDEX = 1
PAINT_TAB_INDEX = 2


def tab_arrow_action(
    tab_index: int, key: int, left_key: int, right_key: int,
) -> tuple[str, int] | None:
    """Return ``(target, direction)`` for a nav-able tab + arrow, else ``None``.

    *target* is ``"modify"`` or ``"paint"``; *direction* is ``-1`` (left /
    previous) or ``+1`` (right / next). Any other tab or any non-arrow key
    yields ``None`` so the event falls through to Qt's default tab-bar handling
    (and Left/Right keep switching tabs on the browse / plugin tabs).
    """
    if key == left_key:
        direction = -1
    elif key == right_key:
        direction = 1
    else:
        return None
    if tab_index == MODIFY_TAB_INDEX:
        return ("modify", direction)
    if tab_index == PAINT_TAB_INDEX:
        return ("paint", direction)
    return None
