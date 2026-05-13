"""Puppet — built-in 2D rigged-puppet animation tab.

Exposes :class:`PuppetWorkspace` for ``Imervue.Imervue_main_window`` to
mount as a main tab. Pure-Qt; the Cubism Native SDK is optional and
gracefully unavailable when the user hasn't supplied the DLL.
"""
from Imervue.puppet.workspace import PuppetWorkspace

__all__ = ["PuppetWorkspace"]
