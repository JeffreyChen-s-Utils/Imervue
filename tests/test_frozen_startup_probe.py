"""The smoke probe must not report source execution as frozen evidence."""

import importlib.util
from pathlib import Path
import sys

import pytest


def _probe():
    path = Path(__file__).resolve().parents[1] / "scripts/frozen_startup_probe.py"
    spec = importlib.util.spec_from_file_location("frozen_startup_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_execution_cannot_report_frozen_success(monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    with pytest.raises(RuntimeError, match="PyInstaller executable"):
        _probe().main()
    assert capsys.readouterr().out == ""


def test_preselected_platform_cannot_report_native_detection(monkeypatch, capsys):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("PYOPENGL_PLATFORM", "nt")
    with pytest.raises(RuntimeError, match="must be unset"):
        _probe().main()
    assert capsys.readouterr().out == ""
