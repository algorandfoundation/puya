# Isolated Sphinx configuration for API-only markdown generation.
# This config is used by docs/api_build.py to generate API reference
# markdown that is consumed by Starlight.

import re

import autodoc2.analysis

# Strip the CPython-style ``S.method(args) -> ret`` signature line that leads
# some ``str`` builtin docstrings (e.g. ``str.endswith``, ``str.format``). The
# rST parser interprets the ``*args``/``**kwargs`` in those lines as malformed
# emphasis/strong markup, which breaks the rendered output. The ``->`` return
# annotation is required so we don't accidentally strip prose that happens to
# start with a function-call-shaped fragment.
_SIG_LINE_RE = re.compile(r"\A(?:S\.)?\w+\([^\n]*?\)\s*->[^\n]*\n+")
_orig_fix_docstring_indent = autodoc2.analysis.fix_docstring_indent


def _stripped_fix_docstring_indent(s, tabsize=8):
    fixed = _orig_fix_docstring_indent(s, tabsize)
    return _SIG_LINE_RE.sub("", fixed, count=1) if fixed else fixed


autodoc2.analysis.fix_docstring_indent = _stripped_fix_docstring_indent

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
autodoc2_hidden_objects = ["private", "dunder"]
# Include docstrings for inherited members too — default "direct" emits the
# heading without the body, leaving e.g. ``stage()`` blank on every concrete
# inner-transaction class even though ``_InnerTransaction.stage`` is documented.
autodoc2_docstrings = "all"
# Parse docstrings as reST (the stubs use ':param:'/':returns:' field-list syntax).
# Without this, autodoc2's MyST plugin emits the raw reST syntax into markdown
# unprocessed; setting "rst" wraps each docstring in an eval-rst block so the
# field lists render as proper Parameters / Returns sections.
autodoc2_docstring_parser_regexes = [(r".+", "rst")]
