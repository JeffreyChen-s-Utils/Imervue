"""Smoke tests for ``.github/workflows/release.yml``.

The release workflow ships a sequence of jobs that publish to PyPI
and create a GitHub Release with the Nuitka-built Windows EXE. We
cannot run the workflow in pytest, but we can lock down the parts a
careless edit would silently break:

* the YAML parses,
* every job exists and is gated on ``check-version.outputs.changed``,
* the version-extraction snippet matches what ``pyproject.toml``
  declares,
* the Nuitka command in the workflow lists the same ``--noinclude``
  / ``--include`` flags that ``nuitka.md`` documents — so a future
  change to one without the other gets caught.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# PyYAML is the only hard runtime dep these workflow assertions need
# but the lean CI image used for the doc / lint matrix doesn't
# install it. Skip the module cleanly rather than failing collection.
yaml = pytest.importorskip("yaml")

# ``tomllib`` is stdlib only on Python 3.11+; the CI matrix still
# includes 3.10, so guard the import. The one test that actually
# parses ``pyproject.toml`` already skips on < 3.11, so a missing
# parser doesn't take the rest of the suite down.
if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow) -> dict:
    return workflow["jobs"]


# ---------------------------------------------------------------------------
# Structural shape — file parses, top-level keys present.
# ---------------------------------------------------------------------------


def test_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_workflow_is_valid_yaml(workflow):
    assert isinstance(workflow, dict)
    assert "jobs" in workflow


def test_triggers_on_push_to_main(workflow):
    # PyYAML decodes the bare-word ``on:`` key as boolean True; tolerate
    # both spellings rather than requiring a ``"on"`` quote in the YAML.
    on = workflow.get("on") or workflow.get(True)
    assert on is not None, "workflow has no trigger block"
    assert "push" in on
    assert on["push"]["branches"] == ["main"]


def test_workflow_default_permissions_are_read_only(workflow):
    """Workflow-scoped token must be read-only — write is reserved
    for the create-release job that actually publishes a tag."""
    assert workflow["permissions"]["contents"] == "read"


def test_create_release_job_grants_contents_write(jobs):
    """The release publisher needs ``contents: write`` to push a tag
    and upload the GitHub Release asset."""
    job_perms = jobs["create-release"].get("permissions", {})
    assert job_perms.get("contents") == "write"


# ---------------------------------------------------------------------------
# Required jobs
# ---------------------------------------------------------------------------


REQUIRED_JOBS = (
    "check-version",
    "publish-pypi",
    "build-exe-windows",
    "create-release",
)


@pytest.mark.parametrize("job_name", REQUIRED_JOBS)
def test_required_job_present(jobs, job_name):
    assert job_name in jobs, f"missing job: {job_name}"


def test_publish_pypi_gated_on_version_change(jobs):
    cond = jobs["publish-pypi"]["if"]
    assert "check-version.outputs.changed" in cond
    assert "true" in cond


def test_build_exe_gated_on_version_change(jobs):
    cond = jobs["build-exe-windows"]["if"]
    assert "check-version.outputs.changed" in cond


def test_create_release_depends_on_pypi_and_exe(jobs):
    needs = jobs["create-release"]["needs"]
    assert "publish-pypi" in needs
    assert "build-exe-windows" in needs


def test_publish_pypi_runs_on_linux(jobs):
    assert jobs["publish-pypi"]["runs-on"] == "ubuntu-latest"


def test_build_exe_runs_on_windows(jobs):
    assert jobs["build-exe-windows"]["runs-on"] == "windows-latest"


# ---------------------------------------------------------------------------
# Version-extraction parity with pyproject.toml
# ---------------------------------------------------------------------------


def test_version_extraction_matches_pyproject_format(jobs):
    """The workflow's version-extraction Python snippet must read the
    same key path that pyproject.toml actually exposes."""
    steps = jobs["check-version"]["steps"]
    read_step = next(s for s in steps if s.get("id") == "read")
    snippet = read_step["run"]
    assert "tomllib" in snippet
    assert "pyproject.toml" in snippet
    assert "['project']['version']" in snippet


def test_pyproject_version_is_extractable():
    """Live sanity check: the snippet's Python code (project →
    version path) must succeed against the current pyproject."""
    if sys.version_info < (3, 11):
        pytest.skip("tomllib needs Python 3.11+")
    with open(PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    assert isinstance(version, str)
    assert version  # non-empty


# ---------------------------------------------------------------------------
# PyPI publish step uses canonical token-auth literals
# ---------------------------------------------------------------------------


def test_twine_upload_uses_token_username(jobs):
    upload_step = next(
        s for s in jobs["publish-pypi"]["steps"]
        if s.get("name") == "Upload to PyPI"
    )
    assert upload_step["env"]["TWINE_USERNAME"] == "__token__"
    # The password must come from a secret, never a literal.
    pw = upload_step["env"]["TWINE_PASSWORD"]
    assert "secrets.PYPI_API_TOKEN" in pw


def test_pypi_step_runs_twine_check_before_upload(jobs):
    """``twine check`` catches malformed long-description metadata
    before we burn an upload slot on PyPI (uploads are immutable)."""
    step_names = [s.get("name") for s in jobs["publish-pypi"]["steps"]]
    check_idx = step_names.index("Verify artifacts")
    upload_idx = step_names.index("Upload to PyPI")
    assert check_idx < upload_idx


# ---------------------------------------------------------------------------
# Nuitka invocation parity with nuitka.md §2.1
# ---------------------------------------------------------------------------


REQUIRED_NUITKA_FLAGS = (
    "--standalone",
    "--windows-console-mode=disable",
    "--enable-plugin=pyside6",
    "--include-package=qt_material",
    "--include-package=imageio",
    "--include-package=rawpy",
    "--include-data-dir=plugins=plugins",
    # Model weights must NEVER ship in the bundle (see nuitka.md §2.4).
    "--noinclude-data-files=plugins/*/models/*",
    "--noinclude-data-files=*.onnx",
    "--noinclude-data-files=*.pt",
    "--noinclude-data-files=*.pth",
    "--noinclude-data-files=*.safetensors",
    "--noinclude-data-files=*.gguf",
    "--module-parameter=torch-disable-jit=yes",
    "--nofollow-import-to=pytest",
    "--nofollow-import-to=doctest",
    "--nofollow-import-to=rembg",
    "--windows-icon-from-ico=exe\\Imervue.ico",
    "--output-dir=build_nuitka",
    "--assume-yes-for-downloads",
)


@pytest.fixture(scope="module")
def nuitka_command(jobs) -> str:
    nuitka_step = next(
        s for s in jobs["build-exe-windows"]["steps"]
        if s.get("name") == "Run Nuitka"
    )
    return nuitka_step["run"]


@pytest.mark.parametrize("flag", REQUIRED_NUITKA_FLAGS)
def test_nuitka_command_includes_flag(nuitka_command, flag):
    assert flag in nuitka_command, f"workflow Nuitka command missing flag: {flag}"


def test_nuitka_command_targets_imervue_package(nuitka_command):
    """Final positional arg must be ``Imervue`` (the package), not
    ``Imervue/__main__.py`` — see nuitka.md §2.1."""
    # Allow trailing whitespace / continuations; just check the token
    # appears as a standalone word.
    tokens = nuitka_command.split()
    assert "Imervue" in tokens
    assert "Imervue/__main__.py" not in tokens
    assert "Imervue\\__main__.py" not in tokens


# ---------------------------------------------------------------------------
# Release-creation step
# ---------------------------------------------------------------------------


def test_release_step_uploads_files(jobs):
    release_steps = jobs["create-release"]["steps"]
    gh_release = next(
        s for s in release_steps
        if "softprops/action-gh-release" in s.get("uses", "")
    )
    assert "files" in gh_release["with"]
    assert gh_release["with"]["tag_name"].startswith(
        "${{ needs.check-version.outputs.tag",
    )


def test_release_downloads_windows_artifact(jobs):
    release_steps = jobs["create-release"]["steps"]
    download = next(
        s for s in release_steps
        if "actions/download-artifact" in s.get("uses", "")
    )
    assert download["with"]["name"] == "imervue-windows-exe"
