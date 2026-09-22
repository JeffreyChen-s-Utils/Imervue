"""The Sphinx docs take their version from pyproject.toml instead of a literal."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_CONF = _REPO / "docs" / "conf.py"

tomllib = pytest.importorskip("tomllib") if sys.version_info >= (3, 11) else None


def _conf() -> dict:
    return runpy.run_path(str(_CONF))


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_release_matches_pyproject():
    with (_REPO / "pyproject.toml").open("rb") as fh:
        expected = tomllib.load(fh)["project"]["version"]
    conf = _conf()
    assert conf["release"] == expected
    assert conf["version"] == ".".join(expected.split(".")[:2])


@pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")
def test_version_reader_handles_missing_file_and_key(tmp_path):
    read = _conf()["_project_version"]
    assert read(tmp_path / "missing.toml") == "unknown"
    no_project = tmp_path / "pyproject.toml"
    no_project.write_text('[tool.x]\ny = 1\n', encoding="utf-8")
    assert read(no_project) == "unknown"
    ok = tmp_path / "ok.toml"
    ok.write_text('[project]\nversion = "2.3.4"\n', encoding="utf-8")
    assert read(ok) == "2.3.4"


def test_updates_log_is_excluded_from_the_build():
    assert "updates" in _conf()["exclude_patterns"]
