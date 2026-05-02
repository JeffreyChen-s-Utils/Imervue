"""Smoke tests for ``.github/workflows/release.yml``.

The release pipeline is a three-job graph:

* ``release``           — bumps version on PR merge, builds the
                          PyPI artefacts, and uploads them.
* ``build-exe-windows`` — produces the standalone Nuitka EXE.
* ``publish-release``   — gathers everything and attaches it to a
                          GitHub Release tagged with the bumped
                          version.

We cannot run the workflow inside pytest, but we can lock down the
shape so a careless edit doesn't silently desync the bump,
PyPI, EXE, and GitHub Release steps.
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

RELEASE_JOB = "release"
BUILD_EXE_JOB = "build-exe-windows"
PUBLISH_JOB = "publish-release"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow) -> dict:
    return workflow["jobs"]


@pytest.fixture(scope="module")
def release_steps(jobs) -> list[dict]:
    return jobs[RELEASE_JOB]["steps"]


@pytest.fixture(scope="module")
def nuitka_command(jobs) -> str:
    nuitka_step = next(
        s for s in jobs[BUILD_EXE_JOB]["steps"]
        if s.get("name") == "Run Nuitka"
    )
    return nuitka_step["run"]


# ---------------------------------------------------------------------------
# Structural shape — file parses, top-level keys present.
# ---------------------------------------------------------------------------


def test_workflow_file_exists():
    assert WORKFLOW_PATH.is_file()


def test_workflow_is_valid_yaml(workflow):
    assert isinstance(workflow, dict)
    assert "jobs" in workflow


def test_triggers_on_pr_merge_to_main(workflow):
    # PyYAML decodes the bare-word ``on:`` key as boolean True; tolerate
    # both spellings rather than requiring a ``"on"`` quote in the YAML.
    on = workflow.get("on") or workflow.get(True)
    assert on is not None, "workflow has no trigger block"
    assert "pull_request" in on
    assert on["pull_request"]["branches"] == ["main"]
    assert "closed" in on["pull_request"]["types"]


def test_workflow_default_permissions_are_read_only(workflow):
    """Workflow-scoped token must be read-only — write is reserved
    for the jobs that actually push tags or create releases."""
    assert workflow["permissions"]["contents"] == "read"


# ---------------------------------------------------------------------------
# Required jobs — graph is release → build-exe-windows → publish-release.
# ---------------------------------------------------------------------------


REQUIRED_JOBS = (RELEASE_JOB, BUILD_EXE_JOB, PUBLISH_JOB)


@pytest.mark.parametrize("job_name", REQUIRED_JOBS)
def test_required_job_present(jobs, job_name):
    assert job_name in jobs, f"missing job: {job_name}"


def test_release_runs_only_when_pr_actually_merged(jobs):
    """Closed-but-not-merged PRs should be a no-op; otherwise dropping
    a PR triggers the release pipeline."""
    cond = jobs[RELEASE_JOB]["if"]
    assert "github.event.pull_request.merged" in cond
    assert "true" in cond


def test_release_runs_on_linux(jobs):
    assert jobs[RELEASE_JOB]["runs-on"] == "ubuntu-latest"


def test_release_grants_contents_write(jobs):
    """The release job pushes the bump commit + tag, so it needs
    ``contents: write`` despite the workflow-level read-only default."""
    assert jobs[RELEASE_JOB]["permissions"]["contents"] == "write"


def test_release_outputs_new_version(jobs):
    """Downstream jobs pin to the freshly-pushed tag via
    ``needs.release.outputs.new`` — losing the output makes the
    Windows-EXE checkout silently fall back to ``main``."""
    outputs = jobs[RELEASE_JOB].get("outputs", {})
    assert "new" in outputs


def test_build_exe_runs_on_windows(jobs):
    assert jobs[BUILD_EXE_JOB]["runs-on"] == "windows-latest"


def test_build_exe_depends_on_release(jobs):
    """The Nuitka build needs the bumped version + tag to exist before
    it checks out, so ``needs: release`` is mandatory."""
    needs = jobs[BUILD_EXE_JOB].get("needs")
    if isinstance(needs, list):
        assert RELEASE_JOB in needs
    else:
        assert needs == RELEASE_JOB


def test_publish_release_runs_on_linux(jobs):
    assert jobs[PUBLISH_JOB]["runs-on"] == "ubuntu-latest"


def test_publish_release_grants_contents_write(jobs):
    """``gh release create`` writes a tag asset so this job needs
    ``contents: write`` even though the bump already happened."""
    assert jobs[PUBLISH_JOB]["permissions"]["contents"] == "write"


def test_publish_release_depends_on_both_upstream_jobs(jobs):
    needs = jobs[PUBLISH_JOB]["needs"]
    assert RELEASE_JOB in needs
    assert BUILD_EXE_JOB in needs


# ---------------------------------------------------------------------------
# Version-bump snippet parity with pyproject.toml
# ---------------------------------------------------------------------------


def test_version_bump_step_targets_pyproject_version(release_steps):
    """The bump-version Python snippet must read & write the same
    ``version = "..."`` line that ``pyproject.toml`` actually exposes."""
    bump_step = next(s for s in release_steps if s.get("id") == "version")
    snippet = bump_step["run"]
    assert "pyproject.toml" in snippet
    assert 'version' in snippet


def test_pyproject_version_is_extractable():
    """Live sanity check: the snippet's regex (``version = "..."``)
    must succeed against the current pyproject."""
    if sys.version_info < (3, 11):
        pytest.skip("tomllib needs Python 3.11+")
    with open(PYPROJECT, "rb") as f:
        data = tomllib.load(f)
    version = data["project"]["version"]
    assert isinstance(version, str)
    assert version  # non-empty


def test_bump_step_reads_pr_labels(release_steps):
    """The major / minor / patch decision pulls from PR labels via
    ``github.event.pull_request.labels.*.name`` — losing that hook
    would silently bury the user's release-type intent."""
    bump_step = next(s for s in release_steps if s.get("id") == "bump")
    env = bump_step.get("env", {})
    labels_expr = env.get("LABELS", "")
    assert "github.event.pull_request.labels" in labels_expr


# ---------------------------------------------------------------------------
# PyPI publish step uses canonical token-auth literals
# ---------------------------------------------------------------------------


def test_twine_upload_uses_token_username(release_steps):
    upload_step = next(
        s for s in release_steps if s.get("name") == "Upload to PyPI with twine"
    )
    assert upload_step["env"]["TWINE_USERNAME"] == "__token__"
    # The password must come from a secret, never a literal.
    pw = upload_step["env"]["TWINE_PASSWORD"]
    assert "secrets.PYPI_API_TOKEN" in pw


def test_upload_runs_twine_check_before_upload(release_steps):
    """``twine check`` catches malformed long-description metadata
    before we burn an upload slot on PyPI (uploads are immutable)."""
    upload_step = next(
        s for s in release_steps if s.get("name") == "Upload to PyPI with twine"
    )
    snippet = upload_step["run"]
    check_idx = snippet.find("twine check")
    upload_idx = snippet.find("twine upload")
    assert 0 <= check_idx < upload_idx, "twine check must precede twine upload"


def test_release_stashes_pypi_artefacts(release_steps):
    """``publish-release`` pulls the wheel + sdist out via
    ``actions/download-artifact``; the release job has to upload
    them under the matching artefact name first."""
    upload_step = next(
        s for s in release_steps
        if "actions/upload-artifact" in s.get("uses", "")
    )
    assert upload_step["with"]["name"] == "pypi-dist"


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


@pytest.mark.parametrize("flag", REQUIRED_NUITKA_FLAGS)
def test_nuitka_command_includes_flag(nuitka_command, flag):
    assert flag in nuitka_command, f"workflow Nuitka command missing flag: {flag}"


def test_nuitka_command_targets_imervue_package(nuitka_command):
    """Final positional arg must be ``Imervue`` (the package), not
    ``Imervue/__main__.py`` — see nuitka.md §2.1."""
    tokens = nuitka_command.split()
    assert "Imervue" in tokens
    assert "Imervue/__main__.py" not in tokens
    assert "Imervue\\__main__.py" not in tokens


def test_build_exe_uploads_zip_artifact(jobs):
    """The publisher downloads under the name ``imervue-windows-exe``;
    the build job has to upload under that exact name."""
    upload_step = next(
        s for s in jobs[BUILD_EXE_JOB]["steps"]
        if "actions/upload-artifact" in s.get("uses", "")
    )
    assert upload_step["with"]["name"] == "imervue-windows-exe"
    # ``if-no-files-found: error`` makes a missing zip fail loud
    # instead of silently publishing an EXE-less release.
    assert upload_step["with"].get("if-no-files-found") == "error"


# ---------------------------------------------------------------------------
# Release-creation step
# ---------------------------------------------------------------------------


def test_release_step_creates_github_release(jobs):
    """The publisher shells out to ``gh release create`` so the tag
    matches the bumped version and release notes are auto-generated."""
    publish_steps = jobs[PUBLISH_JOB]["steps"]
    create_step = next(
        s for s in publish_steps if s.get("name") == "Create GitHub Release"
    )
    snippet = create_step["run"]
    assert "gh release create" in snippet
    assert "${{ needs.release.outputs.new }}" in snippet
    assert "--generate-notes" in snippet


def test_release_attaches_pypi_and_exe_assets(jobs):
    """The ``gh release create`` command must list both the wheel
    bundle (``dist/*``) and the Windows zip (``./release-assets/*.zip``)
    so the published release carries every artefact the pipeline built."""
    publish_steps = jobs[PUBLISH_JOB]["steps"]
    create_step = next(
        s for s in publish_steps if s.get("name") == "Create GitHub Release"
    )
    snippet = create_step["run"]
    assert "dist/*" in snippet
    assert "./release-assets/" in snippet
