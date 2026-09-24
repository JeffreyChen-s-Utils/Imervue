"""Guard: product code never swallows every exception without a trace.

* No ``contextlib.suppress(Exception)`` (or ``BaseException``). ruff's ``BLE``
  rule sees ``except Exception`` but not the ``suppress`` form.
* No broad handler (``except:``, ``except Exception`` / ``BaseException``)
  whose body neither raises, logs, nor uses the bound exception — a
  ``# noqa: BLE001`` silences ruff but not this test.

Catch the exceptions the block can actually meet, or use
``Imervue.system.best_effort.best_effort``, which still carries on but logs the
traceback. Covers ``Imervue/`` and the bundled ``plugins/``.
"""
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_ROOTS = (_REPO / "Imervue", _REPO / "plugins")
_BROAD = {"Exception", "BaseException"}


def _is_suppress(func: ast.expr) -> bool:
    if isinstance(func, ast.Attribute):
        return func.attr == "suppress"
    return isinstance(func, ast.Name) and func.id == "suppress"


def _broad_arg(node: ast.Call) -> str | None:
    for arg in node.args:
        name = arg.attr if isinstance(arg, ast.Attribute) else getattr(arg, "id", None)
        if name in _BROAD:
            return name
    return None


def _silent_suppressions(source: str) -> list[tuple[int, str]]:
    """Return ``(line, exception name)`` for every broad ``suppress(...)`` call in ``source``."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and _is_suppress(node.func):
            broad = _broad_arg(node)
            if broad is not None:
                found.append((node.lineno, broad))
    return found


_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical", "log"}


def _is_broad(node: ast.expr | None) -> bool:
    if node is None:
        return True
    names = node.elts if isinstance(node, ast.Tuple) else [node]
    return any((name.attr if isinstance(name, ast.Attribute) else getattr(name, "id", None))
               in _BROAD for name in names)


def _reports(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _LOG_METHODS):
            return True
        if handler.name and isinstance(node, ast.Name) and node.id == handler.name:
            return True
    return False


def _silent_handlers(source: str) -> list[int]:
    """Return the line of every broad ``except`` in ``source`` that hides the error."""
    return [node.lineno for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ExceptHandler) and _is_broad(node.type)
            and not _reports(node)]


def _product_files():
    for root in _ROOTS:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def test_detector_flags_broad_forms_only():
    source = (
        "import contextlib\n"
        "from contextlib import suppress\n"
        "import builtins\n"
        "with contextlib.suppress(Exception): pass\n"
        "with suppress(OSError, BaseException): pass\n"
        "with contextlib.suppress(builtins.Exception): pass\n"
        "with contextlib.suppress(OSError, ValueError): pass\n"
        "with contextlib.suppress(): pass\n"
    )
    assert _silent_suppressions(source) == [(4, "Exception"), (5, "BaseException"),
                                             (6, "Exception")]


def test_no_product_code_suppresses_every_exception():
    found = [
        f"{path.relative_to(_REPO).as_posix()}:{line} suppress({name})"
        for path in _product_files()
        for line, name in _silent_suppressions(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_handler_detector_flags_silent_broad_handlers_only():
    source = textwrap.dedent("""\
        import logging
        log = logging.getLogger()
        try: pass
        except Exception: pass
        try: pass
        except (OSError, BaseException): x = 1
        try: pass
        except: pass
        try: pass
        except Exception: log.debug('x', exc_info=True)
        try: pass
        except Exception: raise
        try: pass
        except Exception as exc: failures.append(exc)
        try: pass
        except OSError: pass
    """)
    # Silent: plain ``Exception``, ``BaseException`` in a tuple, and a bare ``except``.
    assert _silent_handlers(source) == [4, 6, 8]


def test_no_product_code_hides_a_broad_exception():
    found = [
        f"{path.relative_to(_REPO).as_posix()}:{line}"
        for path in _product_files()
        for line in _silent_handlers(path.read_text(encoding="utf-8"))
    ]
    assert found == []
