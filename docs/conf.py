# ruff: noqa
# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Algorand Python"
copyright = "2024, Algorand Foundation"  # noqa: A001
author = "Algorand Foundation"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "myst_parser",
    "autodoc2",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "architecture-decisions/*.md"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# warning exclusions
suppress_warnings = [
    "myst.xref_missing",
    "autodoc2.dup_item",
]
nitpick_ignore = [
    ("py:class", "algopy.arc4.AllowedOnCompletes"),
]
nitpick_ignore_regex = [
    ("py:class", r"algopy.*\._.*"),
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = [
    "custom.css",
]

python_maximum_signature_line_length = 80

# -- Options for myst ---
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
]

# -- Options for autodoc2 ---
autodoc2_packages = [
    {
        "path": "./algopy-stubs",
        "module": "algopy",
        "auto_mode": False,
    },
]
autodoc2_docstring_parser_regexes = [
    # this will render all docstrings as Markdown
    (r".*", "myst"),
]
autodoc2_hidden_objects = [
    "private",  # single-underscore methods, e.g. _private
    "undoc",
]
autodoc2_class_inheritance = False
autodoc2_module_all_regexes = [r"algopy.*"]
autodoc2_render_plugin = "myst"
autodoc2_sort_names = True
autodoc2_index_template = None
