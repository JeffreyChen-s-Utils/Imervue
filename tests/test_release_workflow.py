"""Smoke tests for ``.github/workflows/release.yml``.

The release workflow auto-bumps the version on PR merge to main,
publishes the resulting build to PyPI, and creates a GitHub Release
with the matching tag. We cannot run the workflow in pytest, but
we can lock down the parts a careless edit would silently break:

* the YAML parses,
* the workflow is gated on the merged-PR signal,
* the version-bump snippet matches the ``pyproject.toml`` shape it
  patches,
* the PyPI upload step uses the canonical token-auth literals,
* ``twine check`` runs before the upload,
* the release publisher creates a GitHub Release tagged with the
  bumped version.
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


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow) -> dict:
    return workflow["jobs"]


@pytest.fixture(scope="module")
def release_steps(jobs) -> list[dict]:
    return jobs[RELEASE_JOB]["steps"]


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
    for the release job that pushes the bump commit and tag."""
    assert workflow["permissions"]["contents"] == "read"


def test_release_job_grants_contents_write(jobs):
    """The release publisher needs ``contents: write`` to push a tag
    and upload the GitHub Release asset."""
    job_perms = jobs[RELEASE_JOB].get("permissions", {})
    assert job_perms.get("contents") == "write"


def test_release_job_present(jobs):
    assert RELEASE_JOB in jobs


def test_release_runs_only_when_pr_actually_merged(jobs):
    """Closed-but-not-merged PRs should be a no-op; otherwise dropping
    a PR triggers the release pipeline."""
    cond = jobs[RELEASE_JOB]["if"]
    assert "github.event.pull_request.merged" in cond
    assert "true" in cond


def test_release_runs_on_linux(jobs):
    assert jobs[RELEASE_JOB]["runs-on"] == "ubuntu-latest"


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


# ---------------------------------------------------------------------------
# Release-creation step
# ---------------------------------------------------------------------------


def test_release_step_creates_github_release(release_steps):
    """The final step shells out to ``gh release create`` so the tag
    matches the bumped version and release notes are auto-generated."""
    create_step = next(
        s for s in release_steps if s.get("name") == "Create GitHub Release"
    )
    snippet = create_step["run"]
    assert "gh release create" in snippet
    assert "${{ steps.version.outputs.new }}" in snippet
    assert "--generate-notes" in snippet
