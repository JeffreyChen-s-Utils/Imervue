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

    def info(self, text: str, duration_ms: int = 2500) -> None:
        self.calls.append(("info", text))

    def success(self, text: str, duration_ms: int = 2500) -> None:
        self.calls.append(("success", text))

    def warning(self, text: str, duration_ms: int = 4000) -> None:
        self.calls.append(("warning", text))

    def error(self, text: str, duration_ms: int = 4000) -> None:
        self.calls.append(("error", text))
