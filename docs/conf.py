# -- Sphinx configuration for Imervue documentation --

project = "Imervue"
author = "Imervue Contributors"
# Sphinx alias for ``copyright`` that avoids shadowing the builtin (Pylint W0622).
project_copyright = "2024-2026, Imervue Contributors"
release = "1.0"

extensions = [
    "sphinx.ext.autosectionlabel",
]

autosectionlabel_prefix_document = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

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
