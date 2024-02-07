# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "PuyaPy"
copyright = "2024, Algorand Foundation"  # noqa: A001
author = "Algorand Foundation"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "autodoc2",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# warning exclusions
suppress_warnings = [
    "myst.xref_missing",
    "autodoc2.dup_item",
]
nitpick_ignore = [
    ("py:class", "puyapy._T"),
    ("py:class", "puyapy._P"),
    ("py:class", "puyapy._R"),
    ("py:class", "puyapy.arc4._T"),
    ("py:class", "puyapy.arc4._TArrayItem"),
    ("py:class", "puyapy.arc4._TTuple"),
]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
# html_static_path = ["_static"]

# -- Options for myst ---
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
]

# -- Options for autodoc2 ---
autodoc2_packages = [
    {"path": "./puyapy-stubs", "module": "puyapy"},
]
autodoc2_docstring_parser_regexes = [
    # this will render all docstrings as Markdown
    (r".*", "myst"),
]
autodoc2_hidden_objects = [
    "private",  # single-underscore methods, e.g. _private
]
autodoc2_class_inheritance = False
autodoc2_module_all_regexes = [r"puyapy"]
autodoc2_render_plugin = "myst"
autodoc2_sort_names = True
autodoc2_index_template = None
