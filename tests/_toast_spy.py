"""Shared toast-spy stub for tests that exercise toast wiring.

Many tests verify that a UI surface forwards success / warning /
error events to ``ToastManager`` without actually constructing one.
This module centralises the recording stand-in so the same spy
isn't redefined in a dozen test files (which used to trip
SonarCloud's duplication detector).

Usage::

    from tests._toast_spy import ToastSpy

    spy = ToastSpy()
    spy.error("oh no")
    assert spy.calls == [("error", "oh no")]
"""
from __future__ import annotations


class ToastSpy:
    """Records every ``info`` / ``success`` / ``warning`` / ``error``
    invocation in a ``calls`` list so tests can assert on the
    severity + body.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    # ``duration_ms`` is part of ToastManager's signature so callers
    # can pass it positionally or by keyword (paint_workspace fires
    # ``toast.info(msg, duration_ms=1200)`` etc.). The spy ignores
    # the value but must keep the keyword name stable so production
    # call sites still resolve under test.
    def info(self, text: str, duration_ms: int = 2500) -> None:  # NOSONAR S1172 - Qt API parity
        self.calls.append(("info", text))

    def success(self, text: str, duration_ms: int = 2500) -> None:  # NOSONAR S1172 - Qt API parity
        self.calls.append(("success", text))

    def warning(self, text: str, duration_ms: int = 4000) -> None:  # NOSONAR S1172 - Qt API parity
        self.calls.append(("warning", text))

    def error(self, text: str, duration_ms: int = 4000) -> None:  # NOSONAR S1172 - Qt API parity
        self.calls.append(("error", text))
