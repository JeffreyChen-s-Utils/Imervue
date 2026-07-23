"""The release workflow pins every dependency it installs — keep it honest.

``release.yml`` installs the Windows-EXE build's runtime dependencies with
explicit ``==`` pins instead of ``-r requirements.txt``: an unpinned resolve
lets a compromised upstream release slip into the published EXE, and the
file's trailing self-reference would pull the very version being replaced.

That buys supply-chain safety at the cost of duplicating the package list, so
these tests fail the moment the workflow and ``requirements.txt`` drift apart.
The workflow itself only runs on a merge to main, which is far too late to
discover the two disagree.
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _ROOT / ".github" / "workflows" / "release.yml"
_REQUIREMENTS = _ROOT / "requirements.txt"

# requirements.txt ends with a self-reference so end users installing from it
# also get the app itself. The build must never install it.
_SELF_REFS = {"imervue", "imervue_dev"}
# Build-only tooling that legitimately appears in the workflow but not in the
# runtime requirements.
_BUILD_TOOLS = {"pip", "wheel", "build", "twine", "nuitka", "ordered_set",
                "zstandard"}
_PIN_RE = re.compile(r'"([A-Za-z0-9_.-]+)==([0-9][^"]*)"')
_BINARY_ONLY = "--only-binary"
# Packages that publish an sdist and no wheel. ``--only-binary :all:`` would
# leave pip with nothing to install, so each is installed on its own; mixing
# one into a wheels-only command is what breaks the release build.
_SDIST_ONLY = {"nuitka"}


def _normalise(name: str) -> str:
    """PyPI treats ``-``/``_`` and case as equivalent; compare on one form."""
    return name.lower().replace("-", "_")


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _runtime_step() -> str:
    """The Windows job's dependency-install step, as raw YAML text."""
    text = _workflow_text()
    start = text.index("- name: Install runtime deps")
    return text[start:text.index("- name: Run Nuitka", start)]


def _install_commands(text: str) -> list[list[str]]:
    """Argument lists of every ``pip install`` invocation in *text*."""
    folded = re.sub(r"\\\n\s*", " ", text)
    commands = []
    for raw in folded.splitlines():
        line = raw.strip()
        marker = "pip install"
        if line.startswith("#") or marker not in line:
            continue
        # Drop a trailing shell comment (a NOSONAR justification, say) so its
        # words are not mistaken for package specs.
        tail = line[line.index(marker) + len(marker):].split(" #", 1)[0]
        args = tail.split()
        commands.append([arg.strip('"') for arg in args])
    return commands


def _packages(args: list[str]) -> list[str]:
    """Package specs from a pip argument list (flags and their values dropped)."""
    return [a for a in args if not a.startswith("-") and a != ":all:"]


def _workflow_pins() -> dict[str, str]:
    return {_normalise(n): v for n, v in _PIN_RE.findall(_runtime_step())}


def _requirement_names() -> set[str]:
    names = set()
    for raw in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = _normalise(re.split(r"[=<>!~\[]", line, maxsplit=1)[0].strip())
        if name not in _SELF_REFS:
            names.add(name)
    return names


def test_install_parser_ignores_a_trailing_shell_comment():
    # A NOSONAR justification sits on the same line as the command; its words
    # must not be read as package specs.
    parsed = _install_commands('  pip install "x==1.0"  # NOSONAR reason here\n')
    assert parsed == [["x==1.0"]]


def test_install_parser_folds_backslash_continuations():
    text = 'pip install --only-binary :all: \\\n  "a==1" \\\n  "b==2"\n'
    assert _install_commands(text) == [["--only-binary", ":all:", "a==1", "b==2"]]


def test_install_parser_skips_commented_out_commands():
    assert _install_commands("# pip install legacy\n") == []


def test_every_runtime_requirement_is_pinned_in_the_build():
    missing = _requirement_names() - set(_workflow_pins())
    assert not missing, f"release.yml does not install: {sorted(missing)}"


def test_workflow_installs_nothing_beyond_requirements_and_build_tools():
    extra = set(_workflow_pins()) - _requirement_names() - _BUILD_TOOLS
    assert not extra, f"release.yml installs unexpected packages: {sorted(extra)}"


def test_pinned_version_matches_when_requirements_also_pins_it():
    # PySide6 is pinned in requirements.txt too; the two must agree or the
    # EXE ships a different Qt than the wheel was tested against.
    assert _workflow_pins()["pyside6"] == "6.11.1"


def test_every_installed_package_carries_an_exact_version():
    unpinned = [
        pkg
        for args in _install_commands(_workflow_text())
        for pkg in _packages(args)
        if "==" not in pkg
    ]
    assert not unpinned, f"unpinned installs in release.yml: {unpinned}"


def test_no_requirements_file_is_installed_unhashed():
    # ``pip install -r`` without --require-hashes is the unlocked-resolve hole
    # this workflow deliberately avoids.
    for args in _install_commands(_workflow_text()):
        if "-r" in args:
            assert "--require-hashes" in args


def _installed_names(args: list[str]) -> set[str]:
    return {_normalise(pkg.split("==")[0]) for pkg in _packages(args)}


def test_windows_build_installs_wheels_only():
    # Source distributions run setup.py at install time; the EXE build must
    # not execute arbitrary upstream code beyond the documented exception.
    installs = [c for c in _install_commands(_runtime_step()) if _packages(c)]
    assert installs, "expected pip installs in the runtime-deps step"
    for args in installs:
        if _installed_names(args) <= _SDIST_ONLY:
            continue
        assert _BINARY_ONLY in args, f"not wheels-only: {_packages(args)}"


def test_sdist_only_packages_are_never_mixed_into_a_wheels_only_install():
    # The failure this guards is concrete: pip resolves nothing for a package
    # with no wheel, so the whole command — and the release — fails.
    for args in _install_commands(_workflow_text()):
        if _BINARY_ONLY in args:
            assert not _installed_names(args) & _SDIST_ONLY


def test_the_app_itself_is_never_installed_by_the_build():
    assert not _SELF_REFS & set(_workflow_pins())


def test_requirements_still_carries_the_self_reference():
    # The comment in release.yml justifies skipping -r by this fact; if the
    # self-reference ever goes away that justification is stale.
    lines = [
        _normalise(line.strip())
        for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert _SELF_REFS & set(lines)
