"""The four dependency lists of the repository must not drift apart.

``pyproject.toml`` is the source of truth. ``dev.toml`` (the ``Imervue_dev``
channel), ``requirements.txt`` and ``dev_requirements.txt`` once lagged it by
three runtime dependencies (imageio-ffmpeg, defusedxml, watchdog).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs Python 3.11+")


def _toml(name: str) -> dict:
    import tomllib
    with (_REPO / name).open("rb") as fh:
        return tomllib.load(fh)


def _requirements(name: str) -> list[str]:
    lines = (_REPO / name).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _runtime_dependencies() -> list[str]:
    return _toml("pyproject.toml")["project"]["dependencies"]


def test_dev_toml_mirrors_pyproject_project_table():
    main = _toml("pyproject.toml")
    dev = _toml("dev.toml")
    assert dev["project"]["name"] == "Imervue_dev"
    for key in ("dependencies", "description", "keywords", "requires-python", "classifiers"):
        assert dev["project"][key] == main["project"][key], key
    assert dev["tool"]["setuptools"]["packages"] == main["tool"]["setuptools"]["packages"]


def test_requirements_txt_lists_runtime_dependencies_then_the_package():
    assert _requirements("requirements.txt") == [*_runtime_dependencies(), "Imervue"]


def test_dev_requirements_cover_runtime_dependencies():
    dev = _requirements("dev_requirements.txt")
    missing = [dep for dep in _runtime_dependencies() if dep not in dev]
    assert missing == []
    assert dev[-1] == "Imervue_dev"
