# Isolated Sphinx configuration for API-only markdown generation.
# This config is used by docs/api_build.py to generate API reference
# markdown that is consumed by Starlight.

import re

import autodoc2.analysis
import autodoc2.db
import autodoc2.render.base

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

# Unhiding dunders (see autodoc2_hidden_objects below) surfaces the authored
# operator overloads, pattern-matching attrs and ``__init_subclass__`` config we
# want — but also pulls in every inherited ``object``/stdlib dunder (``__repr__``,
# ``__hash__``, ``__slots__``, ``__class_getitem__``, …). Hide dunders that are
# inherited rather than authored on the algopy class; authored dunders and
# inherited non-dunder methods (e.g. ``stage()``) are unaffected.
_orig_is_hidden = autodoc2.render.base.RendererBase.is_hidden


def _is_hidden(self, item):
    short = item["full_name"].split(".")[-1]
    if short in ("__all__", "__match_args__", "__match_value__"):
        return True
    if short.startswith("__") and short.endswith("__") and item.get("inherited"):
        return True
    return _orig_is_hidden(self, item)


autodoc2.render.base.RendererBase.is_hidden = _is_hidden

# autodoc2 stashes every ``@overload`` signature aside (db.py InMemoryDb.add),
# expecting a concrete implementation to render them against. Type stubs have no
# implementation, so overload-only methods (e.g. ``Array.__iter__``,
# ``FixedBytes.__ror__``) are dropped entirely. Promote the first *documented*
# overload of such a method so it renders; undocumented overload noise (e.g.
# ``StaticArray.__init__``) stays dropped, and a real implementation (the mixed
# overloads+impl module functions like ``subroutine``) supersedes the promotion.
# ``__init__`` is left to the Initialization injection in api_build.py, which
# preserves all of its overload docstrings.
_orig_db_add = autodoc2.db.InMemoryDb.add


def _db_add(self, item):
    promoted = getattr(self, "_promoted_overloads", None)
    if promoted is None:
        promoted = self._promoted_overloads = set()
    full_name = item["full_name"]
    if item["type"] == "overload":
        if (
            item.get("doc", "").strip()
            and not full_name.endswith(".__init__")
            and full_name not in self._items
        ):
            promoted.add(full_name)
            item = {**item, "type": "method"}
        # otherwise leave it as an overload for the original to stash
    elif full_name in promoted and full_name in self._items:
        # a real implementation supersedes our promoted overload
        self._items.pop(full_name)
        promoted.discard(full_name)
    _orig_db_add(self, item)


autodoc2.db.InMemoryDb.add = _db_add

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
autodoc2_hidden_objects = ["private"]
# Include docstrings for inherited members too — default "direct" emits the
# heading without the body, leaving e.g. ``stage()`` blank on every concrete
# inner-transaction class even though ``_InnerTransaction.stage`` is documented.
autodoc2_docstrings = "all"
# Parse docstrings as reST (the stubs use ':param:'/':returns:' field-list syntax).
# Without this, autodoc2's MyST plugin emits the raw reST syntax into markdown
# unprocessed; setting "rst" wraps each docstring in an eval-rst block so the
# field lists render as proper Parameters / Returns sections.
autodoc2_docstring_parser_regexes = [(r".+", "rst")]
