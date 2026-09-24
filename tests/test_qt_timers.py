"""``call_later`` runs a deferred call unless its owner was destroyed first."""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QObject

from Imervue.system.qt_timers import call_later


def _destroy(obj: QObject) -> None:
    shiboken6.delete(obj)   # now; deleteLater waits for a loop that processEvents never is
    assert not shiboken6.isValid(obj)


def test_runs_while_the_owner_is_alive(qapp, pump_until):
    owner, calls = QObject(), []
    try:
        call_later(0, owner, lambda: calls.append(1))
        assert pump_until(lambda: calls == [1])
    finally:
        _destroy(owner)


def test_is_dropped_once_the_owner_is_destroyed(qapp, pump_until):
    """A bare ``singleShot(ms, lambda)`` still ran here and touched the deleted object."""
    owner, calls = QObject(), []
    call_later(20, owner, lambda: calls.append(1))
    _destroy(owner)
    sentinel = QObject()
    try:
        call_later(60, sentinel, lambda: calls.append("later"))
        assert pump_until(lambda: "later" in calls)
        assert calls == ["later"]
    finally:
        _destroy(sentinel)


def test_non_qobject_owner_still_runs(qapp, pump_until):
    calls = []
    call_later(0, object(), lambda: calls.append(1))
    assert pump_until(lambda: calls == [1])


def test_no_bare_lambda_single_shot_in_the_code():
    """A lambda in ``QTimer.singleShot(ms, lambda: ...)`` outlives its object; use call_later."""
    import ast
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    found = sorted(
        f"{path.relative_to(repo).as_posix()}:{node.lineno}"
        for root in ("Imervue", "plugins") for path in (repo / root).rglob("*.py")
        if "__pycache__" not in path.parts
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "singleShot" and len(node.args) == 2
        and isinstance(node.args[1], ast.Lambda)
    )
    assert found == []


class _Owner(QObject):
    def __init__(self, calls):
        super().__init__()
        self._calls = calls

    def later(self):
        self._calls.append("ran")


def test_a_bare_bound_method_still_runs_after_its_object_is_destroyed(qapp, pump_until):
    """Why bound methods need call_later too: Qt does not tie them to their object."""
    from PySide6.QtCore import QTimer
    calls = []
    owner = _Owner(calls)
    QTimer.singleShot(0, owner.later)
    _destroy(owner)
    assert pump_until(lambda: calls == ["ran"])


def test_call_later_drops_a_bound_method_of_a_destroyed_owner(qapp, pump_until):
    calls = []
    owner = _Owner(calls)
    call_later(20, owner, owner.later)
    _destroy(owner)
    sentinel = QObject()
    try:
        call_later(60, sentinel, lambda: calls.append("later"))
        assert pump_until(lambda: "later" in calls)
        assert calls == ["later"]
    finally:
        _destroy(sentinel)


def test_no_bare_bound_method_single_shot_in_the_app():
    """``QTimer.singleShot(ms, obj.method)`` outlives ``obj``; use call_later(ms, obj, obj.method).

    Plugins keep theirs: they must run on releases that predate call_later.
    """
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "Imervue"
    found = sorted(
        f"{path.relative_to(root.parent).as_posix()}:{node.lineno}"
        for path in root.rglob("*.py") if "__pycache__" not in path.parts
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "singleShot" and len(node.args) == 2
        and isinstance(node.args[1], ast.Attribute)
    )
    assert found == []

