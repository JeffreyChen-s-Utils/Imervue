"""Shared teardown mixin for QDialogs that own background QThread workers.

A dialog that starts a worker thread must stop it before the dialog (and the
thread's underlying C++ object) is destroyed: a ``QThread`` deleted while still
running aborts the process (0xC0000409). The subtle trap is that clicking
*Cancel* calls :meth:`QDialog.reject`, which does **not** deliver a
``closeEvent`` — so a dialog that only cleaned up in ``closeEvent`` leaked the
running thread on every Cancel, and dropping that reference on a bounded
``wait(timeout)`` destroyed a live thread and crashed, most visibly on
cancel-then-reuse.

:class:`WorkerHostMixin` overrides *both* entry points and joins each worker
with an unbounded ``wait()`` so the thread has always finished before its
reference is dropped. Kept Qt-import-free (it only calls duck-typed QThread
methods) so ``_stop_worker`` is unit-testable against a fake worker without a
QApplication.
"""

from __future__ import annotations

import contextlib

_DEFAULT_WORKER_ATTRS = ("_worker",)


_CANCEL_METHODS = ("stop", "abort")


def _stop_and_null(host: object, attr: str) -> None:
    """Stop the worker held on ``host.<attr>`` (if any) and null the slot."""
    worker = getattr(host, attr, None)
    if worker is None:
        return
    if worker.isRunning():
        worker.requestInterruption()
        for name in _CANCEL_METHODS:
            cancel = getattr(worker, name, None)
            if callable(cancel):
                cancel()                     # stop(): kill a child; abort(): set a flag
        with contextlib.suppress(RuntimeError, TypeError):
            worker.disconnect()              # no late signals into a dead dialog
        worker.wait()                        # no timeout: never drop a live thread
    setattr(host, attr, None)


class WorkerHostMixin:
    """Mixin providing crash-safe worker teardown for a ``QDialog``.

    Subclasses keep each running :class:`QThread` on an instance attribute and
    list those attribute names in the class-level ``_worker_attrs`` tuple
    (default ``("_worker",)``). Set the attribute to ``None`` when idle. The
    mixin MUST precede ``QDialog`` in the base list so its ``reject`` /
    ``closeEvent`` win the MRO.

    A worker MAY expose a ``stop()`` and/or ``abort()`` method (to terminate a
    child subprocess or set a cooperative cancel flag); whichever it defines is
    called on teardown so the worker's run loop unblocks and ``wait()`` returns
    promptly instead of hanging until the work finishes.
    """

    _worker_attrs: tuple[str, ...] = _DEFAULT_WORKER_ATTRS

    def _stop_worker(self) -> None:
        """Stop and join every worker this dialog owns, then null its slot."""
        for attr in getattr(self, "_worker_attrs", _DEFAULT_WORKER_ATTRS):
            _stop_and_null(self, attr)

    def reject(self):  # noqa: N802 - Qt API
        self._stop_worker()
        super().reject()

    def closeEvent(self, event):  # noqa: N802 - Qt API  # NOSONAR — QWidget override
        self._stop_worker()
        super().closeEvent(event)
