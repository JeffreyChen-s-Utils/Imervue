"""The lint gates must reach the bundled plugins.

``/plugins/`` is gitignored (its files are force-added), and ruff honours
``.gitignore`` by default, so ``ruff check .`` silently skipped every plugin
until ``respect-gitignore`` was turned off. Bandit only scans the paths it is
given. These checks keep both gates pointed at ``plugins/``.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _ruff_section() -> str:
    # Read without tomllib, which needs Python 3.11 (the CI matrix starts at 3.10).
    text = (_REPO / "pyproject.toml").read_text(encoding="utf-8")
    after = text.split("[tool.ruff]", 1)[1]
    return re.split(r"^\[", after, maxsplit=1, flags=re.MULTILINE)[0]


def test_ruff_does_not_skip_gitignored_plugins():
    assert re.search(r"^respect-gitignore\s*=\s*false\s*$", _ruff_section(), re.MULTILINE)


def test_ci_bandit_scans_the_plugins():
    workflow = (_REPO / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    (command,) = [line.strip() for line in workflow.splitlines() if "-m bandit" in line]
    assert command.endswith("-r Imervue/ plugins/")
