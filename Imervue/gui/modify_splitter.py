"""Sizing of the Modify tab's three-pane splitter (tool strip | canvas | panel).

The centre annotation canvas is inserted between two panes that already share
the full width, so it has to be handed the leftover width explicitly — and
re-handed while the window settles, because ``setSizes`` never recomputes on
its own. The pure arithmetic is module-level; :class:`ModifySplitterMixin`
carries the retry and settle-poll logic for :class:`DevelopPanel`.
"""
from __future__ import annotations

from Imervue.system.qt_timers import call_later

# Preferred width of the right properties panel; also its minimum (see
# build_right_panel). The canvas takes whatever width is left.
RIGHT_PANEL_WIDTH = 260


# Screen-change settle watch for the Modify splitter. A cross-monitor move takes
# hundreds of ms, far longer than the singleShot(0) chain in
# ``_size_modify_splitter`` can span, and ``setSizes`` has no self-healing net.
_SPLITTER_SETTLE_INTERVAL_MS = 60
_SPLITTER_SETTLE_RETRIES = 8


def splitter_is_alive(splitter) -> bool:
    """True while *splitter* still has a live C++ object behind it.

    A deferred settle pass can outlive the Modify tab being torn down; touching
    a freed QSplitter raises ``RuntimeError`` rather than returning anything.
    """
    try:
        splitter.count()
    except RuntimeError:
        return False
    return True


# Floor for the centre canvas so it never collapses to nothing on a narrow
# window — matches the AnnotationCanvas minimum.
MIN_CANVAS_WIDTH = 400


def canvas_splitter_sizes(
    total: int, left: int, right: int, min_canvas: int = MIN_CANVAS_WIDTH,
) -> list[int]:
    """Modify-splitter pane sizes ``[left, canvas, right]``.

    Gives the centre annotation canvas all the width left over after the fixed
    tool strip and the properties panel, floored at *min_canvas*. Without this
    the canvas — inserted between two panes that already shared the full
    width — is squeezed to its minimum and the image opens tiny.
    """
    left = max(0, left)
    right = max(0, right)
    canvas = max(min_canvas, total - left - right)
    return [left, canvas, right]


class ModifySplitterMixin:
    """Sizes the Modify splitter so the canvas gets the leftover width."""

    @staticmethod
    def _apply_modify_splitter_sizes(splitter) -> int:
        """Give the centre canvas the leftover width. Returns the width used.

        Returns ``0`` when the sizing could not be applied — fewer than three
        panes, a splitter destroyed before a deferred pass ran, or a
        not-yet-laid-out zero width — so callers can tell "done" from "retry".
        """
        try:
            if splitter.count() < 3:
                return 0
            total = splitter.width()
        except RuntimeError:
            return 0  # splitter destroyed before this deferred pass
        if total <= 0:
            return 0
        left = splitter.widget(0).sizeHint().width()
        right = max(RIGHT_PANEL_WIDTH, splitter.widget(2).sizeHint().width())
        splitter.setSizes(canvas_splitter_sizes(total, left, right))
        return total

    def _size_modify_splitter(
            self, splitter, _retries: int = 8, _last_total: int = -1) -> None:
        """Give the centre canvas the leftover width so the image isn't tiny.

        The right panel grabbed the full non-tool-strip width while the
        splitter had only two panes, so the freshly-inserted canvas would keep
        just its minimum. Entering Modify right after startup can also read an
        intermediate width before the window/tab has settled, locking in a
        wrong size that no later resize corrects. So re-run on the next turn
        until the width stops changing (bounded), and no-op if the splitter was
        destroyed before a deferred pass ran.

        This chain drains Qt's queued layout and nothing slower — every hop is a
        ``singleShot(0)``. A screen change needs
        :meth:`schedule_modify_splitter_settle` as well.
        """
        total = self._apply_modify_splitter_sizes(splitter)
        if total <= 0:
            if _retries > 0:
                call_later(0, self, lambda: self._size_modify_splitter(splitter, _retries - 1))
            return
        # Layout may still be settling — re-run until the width is stable so an
        # intermediate startup width isn't locked in.
        if total != _last_total and _retries > 0:
            call_later(0, self, lambda: self._size_modify_splitter(splitter, _retries - 1, total))

    def schedule_modify_splitter_settle(
            self, splitter, retries: int = _SPLITTER_SETTLE_RETRIES,
            interval_ms: int = _SPLITTER_SETTLE_INTERVAL_MS) -> None:
        """Keep re-sizing the splitter while the window settles on a new screen.

        ``setSizes`` is one-shot: a later resize rescales whatever proportions
        are already in place rather than recomputing them, so — as this method's
        sibling docstring says — an intermediate width is "locked in wrong and
        no later resize corrects" it. The sibling's ``singleShot(0)`` chain
        cannot prevent that on a screen change, because its whole budget elapses
        in a few event-loop turns while the window takes hundreds of
        milliseconds to land on the new monitor. Polling on a real interval
        spans the settle, so the last pass reads the final width.

        Unlike the deep-zoom canvas there is no per-paint net behind this, which
        is why the watch matters more here than anywhere else.
        """
        from Imervue.gui.settle_poll import poll_settle
        poll_settle(
            lambda: self._apply_modify_splitter_sizes(splitter),
            lambda: splitter_is_alive(splitter),
            retries, interval_ms, owner=splitter,
        )
