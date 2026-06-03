# Isolated Sphinx configuration for API-only markdown generation.
# This config is used by docs/api_build.py to generate API reference
# markdown that is consumed by Starlight.

project = "Algorand Python"
copyright = "2026, Algorand Foundation"
author = "Algorand Foundation"

extensions = ["autodoc2", "myst_parser"]

templates_path = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- autodoc2 configuration ---------------------------------------------------
# Points directly at docs/algopy-stubs/ with a module name override so autodoc2
# sees "algopy" rather than the hyphenated directory name — no staging dir needed.

autodoc2_packages = [
    {
        "path": "../algopy-stubs",
        "module": "algopy",
    }
]
autodoc2_render_plugin = "myst"
autodoc2_output_dir = "apidocs"
autodoc2_hidden_objects = ["private", "dunder", "inherited"]
# Parse docstrings as reST (the stubs use ':param:'/':returns:' field-list syntax).
# Without this, autodoc2's MyST plugin emits the raw reST syntax into markdown
# unprocessed; setting "rst" wraps each docstring in an eval-rst block so the
# field lists render as proper Parameters / Returns sections.
autodoc2_docstring_parser_regexes = [(r".+", "rst")]
