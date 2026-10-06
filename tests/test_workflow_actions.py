"""Every GitHub Actions step pins its action to a commit SHA.

A tag such as ``@v4`` can be moved to new code at any time (the 2025
tj-actions/changed-files compromise rewrote tags), so each ``uses:`` names a
full 40-hex commit and carries the release it corresponds to as a comment,
which is what update tooling reads. Pinning also kept the Node 20 actions from
lingering unnoticed: GitHub removed Node 20 from its runners on 2026-09-23.

The jobs that hold the PyPI token are guarded here too: they install one
hash-locked file and nothing else, and build with the backend locked in it.
Workflows are read as text: PyYAML is not installed on CI.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*\s*$")


def _uses(path: Path) -> list[tuple[int, str, str]]:
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if match:
            found.append((number, match.group(1), match.group(2)))
    return found


def test_workflows_exist():
    assert _WORKFLOWS


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_with_its_version(workflow):
    bad = [f"{workflow.name}:{number} {ref}{rest}"
           for number, ref, rest in _uses(workflow)
           if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))]
    assert bad == []


def test_one_version_per_action():
    # The same action at two different commits means a partial upgrade.
    seen: dict[str, set[str]] = {}
    for workflow in _WORKFLOWS:
        for _number, ref, _rest in _uses(workflow):
            action, _, sha = ref.partition("@")
            seen.setdefault(action, set()).add(sha)
    assert {action: shas for action, shas in seen.items() if len(shas) > 1} == {}


def test_dependabot_keeps_pins_current_on_dev():
    # Pinned SHAs only stay current if something bumps them; every update
    # goes to dev because a push to main runs the release workflow. Parsed as
    # text: PyYAML is not a test dependency.
    text = (_WORKFLOWS[0].parent.parent / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    ecosystems = {block.split()[0].strip("\"'") for block in blocks}
    assert {"pip", "github-actions"} <= ecosystems
    assert all(re.search(r"^\s*target-branch:\s*\"dev\"", block, re.MULTILINE)
               for block in blocks)


def test_dependabot_watches_the_hash_locked_requirements():
    # From "/" Dependabot does not reach .github/requirements/, so the directory
    # has to be named or the lock of the publish jobs is never updated.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    pip = next(block for block in blocks if block.split()[0].strip("\"'") == "pip")
    watched = set(re.findall(r"^\s*-\s*\"(/[^\"]*)\"", pip, re.MULTILINE))
    assert watched == {"/", "/.github/requirements"}


def test_the_docs_job_installs_the_pins_read_the_docs_installs():
    """The docs job names exact pins inline (a requirements file installs unlocked versions
    as far as a scanner can tell); they must stay the ones Read the Docs installs."""
    root = Path(__file__).resolve().parent.parent
    workflow = (root / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    install = next(line for line in workflow.splitlines() if '"sphinx==' in line)
    inline = set(re.findall(r'"([A-Za-z0-9_.-]+==[^"]+)"', install))
    listed = {line.strip() for line in (root / "docs" / "requirements.txt").read_text(
        encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    assert inline == listed


_REQUIREMENTS = _ROOT / ".github" / "requirements"
_LOCKED_INSTALL = ("python -m pip install --require-hashes --only-binary :all: "
                   "-r .github/requirements/publish.txt")
_BUILD_METADATA = ("pyproject.toml", "dev.toml")
_JOB_NAME = re.compile(r"^  ([\w-]+):\s*$", re.MULTILINE)
_PIP_INSTALL = re.compile(r"(?:python3? -m )?\bpip3? install\b.*")
_BUILD = re.compile(r"\bpython3? -m build\b.*")
_RUN_OR_IMPORT = re.compile(
    r"python3? -m ([A-Za-z_]\w*)|^\s*(?:import|from) ([A-Za-z_]\w*)", re.MULTILINE)
_LOCKED_PIN = re.compile(r"^([A-Za-z0-9][\w.-]*)==(\S+)", re.MULTILINE)


def _jobs(workflow: Path) -> list[tuple[str, str]]:
    """Return ``(job name, job text)`` for each job, comment lines and line continuations removed."""
    body = workflow.read_text(encoding="utf-8").split("\njobs:\n", 1)[1]
    parts = _JOB_NAME.split(body)[1:]
    jobs = []
    for name, text in zip(parts[::2], parts[1::2], strict=True):
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        jobs.append((name, re.sub(r"\s*\\\n\s*", " ", code)))
    return jobs


def _token_jobs() -> list[tuple[str, str]]:
    """Return ``(workflow:job, job text)`` for each job that reads the PyPI token."""
    return [(f"{workflow.name}:{name}", body)
            for workflow in _WORKFLOWS
            for name, body in _jobs(workflow)
            if "secrets.PYPI_API_TOKEN" in body]


_TOKEN_JOBS = _token_jobs()
_TOKEN_JOB_IDS = [name for name, _body in _TOKEN_JOBS]


def _distribution(name: str) -> str:
    """Return a module or requirement name the way PyPI spells a distribution."""
    return name.lower().replace("_", "-")


def _named_in(name: str) -> set[str]:
    """Return the distributions a file in ``.github/requirements`` names at the start of a line."""
    text = (_REQUIREMENTS / name).read_text(encoding="utf-8")
    return {_distribution(found) for found in re.findall(r"^([A-Za-z0-9][\w.-]*)", text, re.MULTILINE)}


def _locked() -> dict[str, str]:
    """Return ``{distribution: version}`` for every pin of ``publish.txt``."""
    text = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8")
    return {_distribution(name): version for name, version in _LOCKED_PIN.findall(text)}


def _build_requires(toml_name: str) -> list[Requirement]:
    """Return ``build-system.requires`` of a metadata file (read as text: no tomllib on 3.10)."""
    text = (_ROOT / toml_name).read_text(encoding="utf-8")
    section = text.split("[build-system]", 1)[1].split("\n[", 1)[0]
    items = re.search(r"^requires\s*=\s*\[([^\]]*)\]", section, re.MULTILINE).group(1)
    return [Requirement(item) for item in re.findall(r'"([^"]+)"', items)]


def _tools_run(body: str) -> set[str]:
    """Return what a job runs with ``python -m`` or imports inline, less pip and the stdlib."""
    named = {module or imported for module, imported in _RUN_OR_IMPORT.findall(body)}
    return {_distribution(name) for name in named - {"pip"} - set(sys.stdlib_module_names)}


def test_job_splitter_drops_comments_and_folds_continuations(tmp_path):
    workflow = tmp_path / "w.yml"
    workflow.write_text(
        "on: push\njobs:\n  one:\n    # pip install hidden\n    run: pip install \\\n      a\n"
        "  two-b:\n    run: echo\n", encoding="utf-8")
    assert _jobs(workflow) == [("one", "\n    run: pip install a"), ("two-b", "\n    run: echo")]


def test_the_jobs_that_hold_the_pypi_token_are_the_two_publish_jobs():
    assert _TOKEN_JOB_IDS == ["release.yml:release", "test.yml:publish-dev"]


@pytest.mark.parametrize("body", [body for _name, body in _TOKEN_JOBS], ids=_TOKEN_JOB_IDS)
def test_a_job_with_the_pypi_token_installs_only_the_hash_locked_tooling(body):
    # Whatever these jobs install runs next to the PyPI token. A pin without a
    # hash, or upgrading pip first, trusts whatever the index serves that day;
    # the lock allows only wheels whose hashes were recorded.
    assert [command.strip() for command in _PIP_INSTALL.findall(body)] == [_LOCKED_INSTALL]


@pytest.mark.parametrize("body", [body for _name, body in _TOKEN_JOBS], ids=_TOKEN_JOB_IDS)
def test_a_job_with_the_pypi_token_builds_with_the_locked_backend(body):
    # An isolated build downloads the newest setuptools each time, outside the lock.
    builds = _BUILD.findall(body)
    assert builds
    assert all("--no-isolation" in command.split() for command in builds)


@pytest.mark.parametrize("toml_name", _BUILD_METADATA)
def test_the_lock_satisfies_build_system_requires(toml_name):
    # --no-isolation checks the requirement instead of installing it, so a floor
    # raised without regenerating the lock must fail here, not in the publish job.
    requires = _build_requires(toml_name)
    locked = _locked()
    assert requires
    for requirement in requires:
        name = _distribution(requirement.name)
        assert name in locked, f"{toml_name}: {name} is not pinned in publish.txt"
        assert requirement.specifier.contains(locked[name]), (
            f"{toml_name}: {name}=={locked[name]} fails {requirement.specifier}")


def test_publish_in_lists_exactly_the_tools_and_the_backend():
    # A tool a job starts using has to be locked first, or the release fails at
    # that step; the backend is in the list because the build is not isolated.
    used = set().union(*(_tools_run(body) for _name, body in _TOKEN_JOBS))
    backend = {_distribution(requirement.name)
               for toml_name in _BUILD_METADATA for requirement in _build_requires(toml_name)}
    assert used == {"build", "twine"}
    assert _named_in("publish.in") == used | backend


def test_the_lock_pins_everything_publish_in_names():
    # publish.txt is generated; editing publish.in alone changes nothing the jobs install.
    assert _named_in("publish.in") <= set(_locked())


def test_the_lock_is_wheels_only_and_resolved_for_the_python_the_jobs_set_up():
    # The lock holds the wheels of one Python version; a job on another one may find none.
    command = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8").splitlines()[1]
    assert "--generate-hashes" in command
    assert "--only-binary :all:" in command
    locked_for = re.search(r"--python-version (\S+)", command).group(1)
    set_up = {version for _name, body in _TOKEN_JOBS
              for version in re.findall(r"python-version:\s*\"([^\"]+)\"", body)}
    assert set_up == {locked_for}
