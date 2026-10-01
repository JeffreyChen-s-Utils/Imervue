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


def test_dev_toml_ships_what_pyproject_ships():
    # CI builds Imervue_dev by writing dev.toml to pyproject.toml (scripts/dev_release.py), so
    # anything declared on one side only is a package the tests never ran against.
    main = _toml("pyproject.toml")
    dev = _toml("dev.toml")
    for key in ("optional-dependencies", "scripts", "gui-scripts", "entry-points",
                "license-files", "readme"):
        assert dev["project"].get(key, {}) == main["project"].get(key, {}), key
    assert dev["build-system"] == main["build-system"]
    # Package discovery and package data decide which files reach the wheel.
    assert dev["tool"]["setuptools"] == main["tool"]["setuptools"]


@pytest.mark.parametrize("name", ["pyproject.toml", "dev.toml"])
def test_only_the_imervue_package_is_discovered(name):
    # tests/ has an __init__.py: unrestricted discovery installed it as a top-level ``tests``
    # package, which collides with any other project that ships one.
    find = _toml(name)["tool"]["setuptools"]["packages"]["find"]
    assert find == {"include": ["Imervue", "Imervue.*"], "namespaces": False}


def test_the_include_patterns_leave_out_every_other_top_level_package():
    from fnmatch import fnmatchcase
    include = _toml("pyproject.toml")["tool"]["setuptools"]["packages"]["find"]["include"]
    # What discovery starts from: each top-level directory that is a regular package.
    top_level = {init.parent.name for init in _REPO.glob("*/__init__.py")}
    assert {"Imervue", "tests"} <= top_level
    assert [name for name in sorted(top_level)
            if any(fnmatchcase(name, pattern) for pattern in include)] == ["Imervue"]


def test_the_sdist_keeps_the_whole_test_suite():
    # tests/ is no longer a discovered package, and setuptools alone adds only tests/test_*.py
    # to an sdist: conftest.py and the helper modules would be missing.
    lines = (_REPO / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    assert "recursive-include tests *.py" in lines


def test_every_package_directory_under_imervue_is_shipped():
    # ``namespaces = false`` drops a directory without an __init__.py, with every module in it.
    missing = sorted(
        directory.relative_to(_REPO).as_posix()
        for directory in {path.parent for path in (_REPO / "Imervue").rglob("*.py")}
        if not (directory / "__init__.py").is_file())
    assert missing == []


def test_requirements_txt_lists_runtime_dependencies_then_the_package():
    assert _requirements("requirements.txt") == [*_runtime_dependencies(), "Imervue"]


def test_dev_requirements_cover_runtime_dependencies():
    dev = _requirements("dev_requirements.txt")
    missing = [dep for dep in _runtime_dependencies() if dep not in dev]
    assert missing == []
    assert dev[-1] == "Imervue_dev"
