# -- Sphinx configuration for Imervue documentation --

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10; Read the Docs builds on 3.12
    tomllib = None

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _project_version(pyproject: Path = _PYPROJECT) -> str:
    """Read the package version from pyproject.toml, which CI bumps on every release."""
    if tomllib is None or not pyproject.is_file():
        return "unknown"
    with pyproject.open("rb") as fh:
        return str(tomllib.load(fh).get("project", {}).get("version", "unknown"))


project = "Imervue"
author = "Imervue Contributors"
# Sphinx alias for ``copyright`` that avoids shadowing the builtin (Pylint W0622).
project_copyright = "2024-2026, Imervue Contributors"
release = _project_version()
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autosectionlabel",
]

autosectionlabel_prefix_document = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "updates"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = None
html_favicon = None

# -- Internationalisation ----------------------------------------------------
language = "en"
locale_dirs = ["locale/"]
gettext_compact = False

# -- Options for HTML output -------------------------------------------------
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "titles_only": False,
}
