"""Puppet — built-in 2D rigged-puppet animation tab.

Exposes :class:`PuppetWorkspace` for ``Imervue.Imervue_main_window`` to
mount as a main tab. ``PuppetWorkspace`` pulls in the PySide6 widget / GL
stack, so it is imported lazily through module ``__getattr__``: this keeps the
Qt-free submodules (``document_io``, ``auto_mesh``) importable in headless /
MCP contexts — the ``puppet_from_png`` / ``puppet_inspect`` MCP tools import
``Imervue.puppet.document_io`` and must not drag in Qt.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Imervue.puppet.workspace import PuppetWorkspace

__all__ = ["PuppetWorkspace"]


def __getattr__(name: str):
    if name == "PuppetWorkspace":
        from Imervue.puppet.workspace import PuppetWorkspace
        return PuppetWorkspace
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
