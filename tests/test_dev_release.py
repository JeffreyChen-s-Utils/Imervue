"""``scripts/dev_release.py`` numbers and gates the ``Imervue_dev`` releases CI publishes.

A wrong version is refused by PyPI (a number is never reused) and a wrong comparison either
publishes on every push or never again, so both are pinned here without touching the network.
The ``publish-dev`` job of ``test.yml`` is read as text: PyYAML is not installed on CI.
"""
from __future__ import annotations

import importlib.util
import io
import re
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "dev_release.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
FILES_HOST = "https://files.pythonhosted.org/"
LOCKED_INSTALL = ("python -m pip install --require-hashes --only-binary :all: "
                  "-r .github/requirements/publish.txt")
BUILD_COMMAND = "python -m build --no-isolation"


def _load_script():
    spec = importlib.util.spec_from_file_location("dev_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dev_release = _load_script()


def _wheel(version: str, source: str = "VALUE = 1\n", requires: str = "PySide6==6.11.2") -> bytes:
    info = f"imervue_dev-{version}.dist-info"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Imervue/__init__.py", source)
        archive.writestr(f"{info}/METADATA",
                         f"Name: Imervue_dev\nVersion: {version}\nRequires-Dist: {requires}\n")
        archive.writestr(f"{info}/RECORD", f"Imervue/__init__.py,sha256={version}\n")
        archive.writestr(f"{info}/WHEEL", f"Generator: setuptools ({version})\n")
        archive.writestr(f"{info}/licenses/LICENSE", "MIT\n")
    return buffer.getvalue()


@pytest.mark.parametrize("floor, released, expected", [
    ((1, 0, 9), {(1, 0, 7): None, (1, 0, 6): None}, "1.0.10"),
    ((1, 0, 9), {(1, 0, 9): None}, "1.0.10"),
    ((1, 0, 9), {(1, 0, 14): None}, "1.0.15"),
    ((1, 1, 0), {(1, 0, 14): None}, "1.1.1"),
    ((1, 0, 9), {}, "1.0.10"),
])
def test_next_version_is_one_patch_above_the_floor_and_every_release(floor, released, expected):
    assert dev_release.next_version(floor, released) == expected


def test_published_keeps_plain_releases_and_their_wheels(monkeypatch):
    payload = (
        b'{"releases": {'
        b'"1.0.6": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/a.tar.gz"}],'
        b'"1.0.7": [{"packagetype": "sdist", "url": "https://files.pythonhosted.org/b.tar.gz"},'
        b' {"packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/b.whl"}],'
        b'"1.0.8.dev1": [{"packagetype": "bdist_wheel",'
        b' "url": "https://files.pythonhosted.org/c.whl"}],'
        b'"1.0.5": []}}'
    )
    asked = []
    monkeypatch.setattr(dev_release, "fetch", lambda url: asked.append(url) or payload)

    assert dev_release.published("Imervue_dev") == {
        (1, 0, 6): None,
        (1, 0, 7): FILES_HOST + "b.whl",
    }
    assert asked == ["https://pypi.org/pypi/Imervue_dev/json"]


def test_published_treats_a_project_pypi_does_not_know_as_unreleased(monkeypatch):
    def missing(url):
        raise dev_release.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(dev_release, "fetch", missing)
    assert dev_release.published("Imervue_dev") == {}


def test_published_does_not_hide_a_pypi_outage(monkeypatch):
    def unavailable(url):
        raise dev_release.HTTPError(url, 503, "Service Unavailable", None, None)

    monkeypatch.setattr(dev_release, "fetch", unavailable)
    with pytest.raises(dev_release.HTTPError):
        dev_release.published("Imervue_dev")


def test_fetch_refuses_a_host_that_is_not_pypi():
    with pytest.raises(ValueError, match="refusing to fetch"):
        dev_release.fetch("https://example.com/imervue_dev.whl")


def test_prepare_writes_pyproject_from_dev_toml_with_the_next_version(tmp_path, monkeypatch):
    dev_toml = (REPO_ROOT / "dev.toml").read_text(encoding="utf-8")
    (tmp_path / "dev.toml").write_text(dev_toml, encoding="utf-8")
    asked = []
    monkeypatch.setattr(dev_release, "published",
                        lambda name: asked.append(name) or {(9, 9, 9): None})

    assert dev_release.prepare(tmp_path) == "9.9.10"

    written = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert asked == ["Imervue_dev"]
    assert written == dev_release.VERSION_LINE.sub(r'\g<1>"9.9.10"', dev_toml, count=1)
    assert written.count('version = "9.9.10"') == 1


def test_prepare_refuses_a_dev_toml_without_a_plain_version(tmp_path):
    (tmp_path / "dev.toml").write_text('[project]\nname = "Imervue_dev"\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        dev_release.prepare(tmp_path)
    assert not (tmp_path / "pyproject.toml").exists()


def test_fingerprint_ignores_what_only_the_version_number_changes():
    assert dev_release.fingerprint(_wheel("1.0.9")) == dev_release.fingerprint(_wheel("1.0.10"))


@pytest.mark.parametrize("difference", [{"source": "VALUE = 2\n"}, {"requires": "PySide6==6.11.3"}])
def test_fingerprint_sees_changed_code_and_changed_metadata(difference):
    assert dev_release.fingerprint(_wheel("1.0.9")) != dev_release.fingerprint(
        _wheel("1.0.10", **difference))


@pytest.mark.parametrize("latest, expected", [
    ({}, True),
    ({"source": "VALUE = 0\n"}, True),
    ({"source": "VALUE = 1\n"}, False),
])
def test_changed_compares_the_built_wheel_with_the_newest_published_one(
        tmp_path, monkeypatch, latest, expected):
    # setuptools writes the normalised project name into the file name: ``imervue_dev``.
    (tmp_path / "imervue_dev-1.0.10-py3-none-any.whl").write_bytes(_wheel("1.0.10"))
    url = FILES_HOST + "imervue_dev-1.0.9-py3-none-any.whl"
    released = {(1, 0, 8): FILES_HOST + "old.whl", (1, 0, 9): url} if latest else {}
    asked = []
    monkeypatch.setattr(dev_release, "published", lambda name: asked.append(name) or released)
    monkeypatch.setattr(dev_release, "fetch",
                        lambda wanted: _wheel("1.0.9", **latest) if wanted == url else b"")

    assert dev_release.changed(tmp_path) is expected
    assert asked == ["imervue_dev"]


def test_changed_publishes_when_the_newest_release_has_no_wheel(tmp_path, monkeypatch):
    (tmp_path / "imervue_dev-1.0.10-py3-none-any.whl").write_bytes(_wheel("1.0.10"))
    monkeypatch.setattr(dev_release, "published", lambda name: {(1, 0, 9): None})

    assert dev_release.changed(tmp_path) is True


def test_main_writes_the_result_where_the_workflow_reads_it(tmp_path, monkeypatch):
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(dev_release, "changed", lambda dist: False)

    assert dev_release.main(["changed", str(tmp_path)]) == 0
    assert output.read_text(encoding="utf-8") == "changed=false\n"
    assert dev_release.main(["publish"]) == 2


def test_main_prepare_prints_the_version_it_wrote(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dev_release, "prepare", lambda root: f"1.0.10 in {root.name}")

    assert dev_release.main(["prepare"]) == 0
    assert capsys.readouterr().out == f"version=1.0.10 in {tmp_path.name}\n"


def _jobs() -> str:
    return WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]


def _publish_job() -> str:
    return re.split(r"^  publish-dev:\s*$", _jobs(), maxsplit=1, flags=re.MULTILINE)[1]


def test_the_workflow_publishes_only_a_tested_push_to_dev():
    # test.yml also runs for main and for pull requests; the condition keeps both out.
    job = _publish_job()
    assert re.findall(r"^  ([\w-]+):\s*$", _jobs(), flags=re.MULTILINE) == [
        "lint", "docs", "fast", "extended", "real-gl", "publish-dev"]
    assert "needs: [lint, docs, fast, extended, real-gl]" in job
    assert "if: github.event_name == 'push' && github.ref == 'refs/heads/dev'" in job


def test_the_workflow_uploads_only_a_changed_build_and_keeps_no_credentials():
    job = _publish_job()
    upload = job.index("twine upload")
    assert job.index("dev_release.py prepare") < job.index(BUILD_COMMAND) < upload
    assert job.index("twine check dist/*") < upload
    assert job.index("dev_release.py changed dist") < upload
    assert job.index("git ls-remote origin refs/heads/dev") < upload
    assert ("if: steps.compare.outputs.changed == 'true' && steps.tip.outputs.current == 'true'"
            in job)
    assert "persist-credentials: false" in job


def test_the_workflow_builds_with_the_tooling_of_the_stable_release():
    # Both jobs install the one hash-locked file and build without isolation, so build, twine
    # and the build backend are the same versions; a dev package built by other versions
    # would not be the package the stable release builds.
    release = RELEASE_WORKFLOW.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    release_job = release.split("\n  build-exe-windows:", 1)[0]
    for job in (_publish_job(), release_job):
        assert job.count(LOCKED_INSTALL) == 1
        assert job.count("python -m build") == job.count(BUILD_COMMAND) == 1
        assert job.index(LOCKED_INSTALL) < job.index(BUILD_COMMAND) < job.index("twine check")
        # No version named beside the lock: a second pin would be a second truth.
        assert re.findall(r'"(?:pip|build|twine|setuptools)==[^"]+"', job) == []
