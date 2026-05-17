"""Shared headless-CI skip marker for Qt-heavy test modules.

QOpenGLWidget construction segfaults on the headless GitHub Actions
Windows runner once the offscreen-GL pool is exhausted. Test modules
that touch a real ``PuppetCanvas`` / ``PuppetWorkspace`` import this
as their module-level ``pytestmark``; local runs still cover them.
Centralised here so the gate condition lives in one place instead of
being copy-pasted into every test file.
"""
import os

import pytest

# Exported as ``pytestmark`` so test modules can simply do
# ``from _qt_skip import pytestmark`` and pytest picks it up as
# the module-level marker. This file itself does not match the
# ``test_*.py`` collection glob, so pytest never inspects it as a
# test module — the name is only meaningful at the import site.
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true"
    or os.environ.get("QT_QPA_PLATFORM") == "offscreen",
    reason="QOpenGLWidget construction segfaults on headless CI runner",
)
