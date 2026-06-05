#!/usr/bin/env python3
"""Generate API reference markdown from algopy stubs, then post-process for Starlight.

Pipeline:
  1. Run scripts/generate_docs.output_doc_stubs() to produce processed .pyi files
     in docs/algopy-stubs/ (reuses the existing mypy-based stub processing).
  2. Run sphinx-build -b markdown against docs/sphinx/ to generate raw markdown.
     sphinx-autodoc2 reads docs/algopy-stubs/ directly (module name overridden to
     "algopy" in conf.py), so no staging directory is required.
  3. Post-process the markdown for Starlight compatibility:
     - Inject YAML frontmatter (title)
     - Strip duplicate H1 headings
     - Flatten autodoc2 output directory
     - Fix /index.md links
     - Shorten fully-qualified names in H3/H4 headings
     - Simplify *class* headings (strip constructor signatures)
     - Rewrite Sphinx-style qualified anchors to Starlight heading IDs
"""

from __future__ import annotations

import ast
import functools
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
# Sphinx writes its raw markdown into a scratch directory outside the Astro
# content tree so the dev server's file watcher doesn't see partial / pre-
# frontmatter files mid-build (which would surface as transient
# InvalidContentEntryDataError logs).
SPHINX_OUT = DOCS_DIR / ".api_build_tmp"
API_OUT = DOCS_DIR / "src" / "content" / "docs" / "api"
PACKAGE_NAME = "algopy"
_pkg = re.escape(PACKAGE_NAME)

# Regex patterns ----------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{3,4}\s")

_LINKED_QUALIFIED_RE = re.compile(
    r"\[(?:" + _pkg + r"|typing_extensions|collections\.abc)"
    r"(?:\.\w+)*\.(\w+)\]"
)
_PLAIN_QUALIFIED_RE = re.compile(
    r"(?<!\[)(?<!#)(?<!/)(?<!\.md)(?<!\()"
    r"(?:" + _pkg + r"|typing_extensions|collections\.abc)"
    r"(?:\.\w+)*\.(\w+)"
)

# Matches relative algopy*.md references in links, e.g. (algopy.op.md) or (algopy.md#class-foo)
_MODULE_MD_LINK_RE = re.compile(r"\(algopy(?:\.(\w+))?\.md(#[^)]+)?\)")

# Base URL path for the site (must match base in astro.config.mjs)
_SITE_BASE = "/puya/"

# Matches *class* headings with constructor signatures:
# "### *class* Foo(\*args, \*\*kwds)"
_CLASS_ARGS_RE = re.compile(
    r"^(#{3,4} \*class\* (\w+))(\(.*\))[ \t]*\n",
    re.MULTILINE,
)

# Matches function/method headings with signatures, e.g.
# "### compile_contract(contract: type[...], ...) → CompiledContract"
# "#### copy() → Self"
# The leading ``*kind*`` token (``*staticmethod*``, ``*async*``, …) is
# captured so it can be preserved on the heading line. ``*class*``,
# ``*property*`` and ``*classmethod*`` headings don't take parens so they
# won't match.
_FUNC_SIG_RE = re.compile(
    r"^(?P<hashes>#{3,4}) "
    r"(?P<kind>(?:\*(?:staticmethod|classmethod|abstractmethod|async)\* )*)"
    r"(?P<name>[\w.\\]+)"  # allow ``\`` so escaped dunder names (\_\_eq_\_) lift too
    r"(?P<sig>\(.*)$",
    re.MULTILINE,
)

_H3_TEXT_RE = re.compile(r"^### (.+)$", re.MULTILINE)

_QUALIFIED_ANCHOR_RE = re.compile(
    r"\(([^()\s\"']*?)#(?:" + _pkg + r"|typing_extensions|collections\.abc)"
    r"(?:\.\w+)*\.(\w+)\)"
)

# Path to the autoapi source stubs that sphinx reads (see docs/sphinx/conf.py).
_AUTOAPI_SRC = DOCS_DIR / "algopy-stubs"

# Triple-backtick fence with matching indent on the closing line. The info
# string after the opening fence may be a language hint (```python), a MyST
# directive ({note}), or empty.
_FENCE_RE = re.compile(
    r"^(?P<indent>[ \t]*)```(?P<info>[^\n]*)\n(?P<body>.*?)\n(?P=indent)```",
    re.MULTILINE | re.DOTALL,
)

# Triple-quoted docstring; non-greedy so each docstring is captured separately.
_DOCSTRING_RE = re.compile(r'(""")(.*?)(""")', re.DOTALL)

# Bare `TMPL_` references in docstrings render as plain text in Sphinx; wrap
# them in rST inline-code so they appear as code in the rendered API docs.
_TMPL_PREFIX_RE = re.compile(r"\bTMPL_\b")

# Single-backtick spans (markdown-style inline code). Sphinx's rST mode treats
# them as the unresolved default role and falls through to plain text — promote
# to double-backtick rST inline literals. Excludes spans preceded by ``:`` (rST
# roles like ``:ref:`x```) or an adjacent backtick (already double).
_INLINE_BACKTICK_RE = re.compile(r"(?<![:`])`([^`\n]+?)`(?!`)")


# Step 1: stub generation -------------------------------------------------------


def _generate_stubs() -> None:
    """Run the existing stub processing from scripts/generate_docs.py.

    Reuses the mypy-based logic that processes stubs/algopy-stubs/ and writes
    combined .pyi files to docs/algopy-stubs/. This avoids duplicating the
    complex protocol-inlining and symbol-collection logic.
    """
    print("==> Generating algopy stubs...")
    sys.path.insert(0, str(REPO_ROOT))

    # These imports require the full puya dev environment (uv run).
    import mypy.build
    import mypy.find_sources

    from puya.log import configure_stdio
    from puyapy.parse import _get_mypy_options
    from scripts.generate_docs import output_doc_stubs

    configure_stdio()
    opts = _get_mypy_options()
    opts.python_executable = sys.executable
    stubs_dir = REPO_ROOT / "stubs" / "algopy-stubs"
    sources = mypy.find_sources.create_source_list([str(stubs_dir)], opts)
    result = mypy.build.build(sources, options=opts)
    output_doc_stubs(result.manager)


# Step 1.5: docstring preprocessing --------------------------------------------


def _fence_to_directive(m: re.Match[str]) -> str:
    """Replace a markdown fence with the equivalent rST directive."""
    indent = m.group("indent")
    info = m.group("info").strip()
    body = m.group("body")
    if info.startswith("{") and info.endswith("}"):
        directive = f"{indent}.. {info[1:-1].strip()}::"
    elif info:
        directive = f"{indent}.. code-block:: {info}"
    else:
        directive = f"{indent}.. code-block::"
    body_indent = indent + "   "
    raw_lines = body.split("\n")
    non_blank = [ln for ln in raw_lines if ln.strip()]
    common = min((len(ln) - len(ln.lstrip(" \t")) for ln in non_blank), default=0)
    body_lines = [body_indent + ln[common:] if ln.strip() else "" for ln in raw_lines]
    # Leading newline ensures the directive is preceded by a blank line — rST
    # parsers otherwise treat it as a continuation of the previous paragraph
    # (e.g. "Example:\n.. code-block::" coalesces into "Example: .. code-block:").
    return f"\n{directive}\n\n" + "\n".join(body_lines)


def _rewrite_fences_in_docstring(m: re.Match[str]) -> str:
    open_q, body, close_q = m.group(1), m.group(2), m.group(3)
    body = _FENCE_RE.sub(_fence_to_directive, body)
    body = _TMPL_PREFIX_RE.sub("``TMPL_``", body)
    body = _INLINE_BACKTICK_RE.sub(r"``\1``", body)
    return f"{open_q}{body}{close_q}"


def _preprocess_docstrings() -> None:
    """Translate markdown fences in docstrings to rST directives.

    The rST docstring parser configured in docs/sphinx/conf.py handles
    :param:/:returns: field lists, but treats markdown ``` fences as raw
    text. Rewrite them in the autoapi source .pyi files before sphinx runs:

      ``​```{note}\n...\n```​``  →  ``.. note::``
      ``​```python\n...\n```​``  →  ``.. code-block:: python``
      ``​```\n...\n```​``        →  ``.. code-block::``
    """
    print("==> Preprocessing docstrings (markdown fences -> rST)...")
    for pyi in sorted(_AUTOAPI_SRC.rglob("*.pyi")):
        text = pyi.read_text(encoding="utf-8")
        new_text = _DOCSTRING_RE.sub(_rewrite_fences_in_docstring, text)
        if new_text != text:
            pyi.write_text(new_text, encoding="utf-8")


# Step 2: Sphinx markdown build -------------------------------------------------


def _clean_sphinx_out() -> None:
    print("==> Cleaning sphinx scratch directory...")
    if SPHINX_OUT.exists():
        shutil.rmtree(SPHINX_OUT)
    SPHINX_OUT.mkdir(parents=True, exist_ok=True)


def _run_sphinx_build() -> None:
    print("==> Running Sphinx markdown build...")
    result = subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "doc",
            "sphinx-build",
            "-b",
            "markdown",
            "docs/sphinx",
            str(SPHINX_OUT),
            "-q",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: Sphinx build failed (exit {result.returncode})", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        sys.exit(1)


# Step 4: post-processing -------------------------------------------------------


def _remove_sphinx_artifacts() -> None:
    print("==> Removing Sphinx artifacts...")
    for name in [".buildinfo"]:
        p = SPHINX_OUT / name
        if p.exists():
            p.unlink()
    doctrees = SPHINX_OUT / ".doctrees"
    if doctrees.exists():
        shutil.rmtree(doctrees)
    # Drop the top-level index.md generated from index.rst (not used by Starlight).
    index_md = SPHINX_OUT / "index.md"
    if index_md.exists():
        index_md.unlink()


def _flatten_autoapi() -> None:
    """Move apidocs/<package>/ up one level inside the sphinx scratch dir."""
    print("==> Flattening autodoc2 directory structure...")
    autodoc2_pkg = SPHINX_OUT / "apidocs" / PACKAGE_NAME
    target = SPHINX_OUT / PACKAGE_NAME

    if not autodoc2_pkg.is_dir():
        print(
            f"ERROR: Expected autodoc2 output directory not found: {autodoc2_pkg}\n"
            "Check that 'autodoc2_output_dir' in docs/sphinx/conf.py is set to 'apidocs'.",
            file=sys.stderr,
        )
        sys.exit(1)

    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(autodoc2_pkg), str(target))

    apidocs_dir = SPHINX_OUT / "apidocs"
    if apidocs_dir.exists():
        shutil.rmtree(apidocs_dir)


def _extract_title_from_content(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            # Strip markdown link syntax: [`foo`](#anchor) → foo, [foo](#anchor) → foo
            return re.sub(r"\[`?([^`\]]+)`?\]\([^)]*\)", r"\1", title)
    return None


def _inject_frontmatter(path: Path, content: str) -> str:
    title = _extract_title_from_content(content) or path.stem
    escaped = title.replace('"', '\\"')
    # Strip the H1 — Starlight renders title from frontmatter.
    content = re.sub(r"^# [^\n]*\n+", "", content)
    return f'---\ntitle: "{escaped}"\n---\n\n<div class="api-ref">\n\n{content}\n\n</div>\n'


def _fix_module_md_links(content: str) -> str:
    """Rewrite relative algopy*.md links to absolute Starlight URLs.

    Sphinx/autodoc2 outputs relative links like (algopy.op.md#class-txn), but
    Starlight slugifies dots away when generating page URLs, so 'algopy.op.md'
    becomes the slug 'algopyop' (URL /puya/api/algopy/algopyop/). Relative links
    from a sibling page therefore resolve to the wrong URL.
    """

    def _md_to_url(m: re.Match) -> str:
        module_suffix = m.group(1)  # 'op', 'arc4', etc., or None for algopy itself
        anchor = m.group(2) or ""  # '#class-foo' or ''
        stem = f"algopy{module_suffix}" if module_suffix else "algopy"
        slug = stem.replace(".", "")
        return f"({_SITE_BASE}api/algopy/{slug}/{anchor})"

    return _MODULE_MD_LINK_RE.sub(_md_to_url, content)


def _shorten_qualified_names(content: str) -> str:
    """Strip module prefixes from H3/H4 headings (e.g. algopy.arc4.Address → Address)."""
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not _HEADING_RE.match(line):
            continue
        new_line = _LINKED_QUALIFIED_RE.sub(r"[\1]", line)
        new_line = _PLAIN_QUALIFIED_RE.sub(r"\1", new_line)
        if new_line != line:
            lines[i] = new_line
    return "".join(lines)


# A markdown link whose target is a bare URL gets the URL auto-linkified by myst,
# producing a broken nested link: ``[text]([url](url))``.
_NESTED_LINK_RE = re.compile(r"\]\(\[[^\]]+\]\((https?://[^)]+)\)\)")


def _collapse_nested_links(content: str) -> str:
    """Collapse myst's nested ``[text]([url](url))`` links back to ``[text](url)``."""
    return _NESTED_LINK_RE.sub(r"](\1)", content)


# autodoc2 emits member-summary tables with no header row, so Markdown treats
# the first member row as the header (rendered bold). Insert a ``Name | Description``
# header so the first member renders as a normal body row.
_SUMMARY_TABLE_RE = re.compile(r"(?m)^(\| \[.*\|)\n(\|[-\s|]+\|)$")


def _fix_summary_table_headers(content: str) -> str:
    return _SUMMARY_TABLE_RE.sub(r"| Name | Description |\n\g<2>\n\g<1>", content)


def _strip_default_language(content: str) -> str:
    """Remove the ``default`` language tag from fenced code blocks.

    Sphinx-markdown-builder writes ``.. code-block::`` (no argument) as
    ``` ```default ```; Starlight's expressive-code highlighter doesn't know
    that language and falls back to plain text with a warning. Drop the tag
    so the block renders as plain text without the warning.
    """
    return re.sub(r"^```default\s*$", "```", content, flags=re.MULTILINE)


def _compute_starlight_anchor(heading_text: str) -> str:
    """Compute the anchor slug that Starlight/rehype-slug generates from heading text."""
    text = re.sub(r"\*([^*]+)\*", r"\1", heading_text)   # *em* → em
    text = re.sub(r"`([^`]+)`", r"\1", text)              # `code` → code
    text = re.sub(r"\\.", "", text)                        # \* → (removed)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)  # [text](url) → text
    text = text.lower()
    text = re.sub(r"[^a-z0-9-]+", " ", text)
    return "-".join(text.split())


def _github_slug(heading_text: str) -> str:
    """Compute the anchor slug that Starlight/github-slugger generates from heading text.

    github-slugger algorithm (used by rehype-slug in Starlight):
    1. Strip markdown syntax (links, emphasis, code, backslash escapes)
    2. Lowercase
    3. Replace underscore with hyphen
    4. Remove all chars not in [a-z0-9 space hyphen] individually (no replacement char)
    5. Replace spaces with hyphens
    6. Do NOT collapse multiple consecutive hyphens
    7. Strip leading/trailing hyphens

    This differs from _compute_starlight_anchor() which collapses runs of
    non-alphanumeric chars into a single space (producing single hyphens), while
    github-slugger removes them individually, preserving surrounding spaces as
    separate hyphens (e.g. ' | ' → ' ' + ' ' → '--').
    """
    # Strip markdown syntax
    text = re.sub(r"\*([^*]+)\*", r"\1", heading_text)    # *em* → em
    text = re.sub(r"`([^`]+)`", r"\1", text)               # `code` → code
    text = re.sub(r"\\(.)", r"\1", text)                    # \_t → _t (keep escaped char)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)   # [text](url) → text
    # Lowercase
    text = text.lower()
    # Remove all chars not in [a-z0-9 _-] individually (no replacement character)
    # Note: underscores are preserved by github-slugger (not converted to hyphens)
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    # Spaces → hyphens (preserving doubles from e.g. ' | ' → '  ' → '--')
    text = text.replace(" ", "-")
    # Strip leading/trailing hyphens
    return text.strip("-")


def _simplify_class_headings(content: str) -> str:
    """Lift constructor signatures out of *class* headings into a sibling block.

    Converts: ### *class* Foo(value: int = 0, /)
    To:        ### *class* Foo

               <div class="api-signature">Foo(value: int = 0, /)</div>

    Keeps the constructor signature visible while giving the heading a clean,
    predictable anchor (``#class-foo``) that matches summary-table links — without
    it Starlight emits messy anchors like ``#class-foo-value-int-0``.
    """

    def sub(m: re.Match[str]) -> str:
        heading, name, args = m.group(1), m.group(2), m.group(3)
        return f'{heading}\n\n<div class="api-signature">\n\n{name}{args}\n\n</div>\n'

    return _CLASS_ARGS_RE.sub(sub, content)


_CLASS_HEADING_RE = re.compile(r"^### \*class\* (\w+)")
_H4_HEADING_RE = re.compile(
    r"^#### (?P<kind>(?:\*\w+\* )+)?(?P<name>[\w\\]+)(?P<rest>.*)$"
)


def _qualify_method_headings(content: str) -> str:
    """Prefix H4 method headings with their enclosing class name.

    Rewrites:
        ### *class* FixedArray
        ...
        #### copy() → Self
    Into:
        ### *class* FixedArray
        ...
        #### FixedArray.copy() → Self

    Without this, methods sharing a name across classes (``copy`` on every
    array/struct type) all collapse to ``#copy``/``#copy-1``/``#copy-2`` via
    github-slugger's order-dependent dedup. Qualifying with the class name
    yields stable, unique anchors like ``#fixedarraycopy`` that survive
    reordering of class declarations.
    """
    lines = content.splitlines()
    current_class: str | None = None
    for i, line in enumerate(lines):
        m = _CLASS_HEADING_RE.match(line)
        if m:
            current_class = m.group(1)
            continue
        # Note: don't reset on non-class H3s. autoapi emits ``### Initialization``
        # as a sub-section under each class — methods that follow still belong
        # to the most recent ``### *class* Foo``. Top-level functions render as
        # H3 (not H4), so they aren't matched here regardless of context.
        if current_class is None:
            continue
        hm = _H4_HEADING_RE.match(line)
        if not hm:
            continue
        name = hm.group("name")
        # Don't re-qualify (e.g. ``FixedArray.copy`` already qualified) or
        # touch private names emitted by autoapi.
        if name.startswith("_") or "." in name:
            continue
        kind = hm.group("kind") or ""
        rest = hm.group("rest")
        lines[i] = f"#### {kind}{current_class}.{name}{rest}"
    return "\n".join(lines)


def _split_function_signatures(content: str) -> str:
    """Lift function/method signatures out of headings into a sibling line.

    Converts: ### compile_contract(contract: type[...], ...) → CompiledContract
    To:
        ### compile_contract

        <div class="api-signature">compile_contract(contract: type[...], ...) → CompiledContract</div>

    Keeps the signature visible (with its embedded type cross-reference links
    intact) but gives the heading a clean slug like ``#compile_contract``
    instead of a 200-character anchor that includes the full parameter list.
    Method-name collisions on the same page (e.g. ``stage`` on every inner
    transaction class) are deduplicated by github-slugger with ``-1``/``-2``
    suffixes; :func:`_fix_member_index_anchors` keeps same-page references in
    sync.
    """
    def sub(m: re.Match[str]) -> str:
        hashes = m.group("hashes")
        kind = m.group("kind") or ""
        name = m.group("name")
        sig = m.group("sig")
        return (
            f"{hashes} {kind}{name}\n\n"
            f'<div class="api-signature">\n\n'
            f"{name}{sig}\n\n"
            f"</div>"
        )

    return _FUNC_SIG_RE.sub(sub, content)


_CLASS_BLOCK_RE = re.compile(r"(?ms)^(### \*class\* (\w+)\b.*?)(?=^### \*class\* |\Z)")
_MEMBER_HEADING_RE = re.compile(r"(?m)^#{3,4} ")


@functools.cache
def _init_docstrings_by_class() -> dict[str, str]:
    docs: dict[str, str] = {}
    for pyi in sorted(_AUTOAPI_SRC.glob("*.pyi")):
        for node in ast.walk(ast.parse(pyi.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name not in docs:
                paras = dict.fromkeys(
                    ast.get_docstring(n, clean=True) or ""
                    for n in node.body
                    if isinstance(n, ast.FunctionDef) and n.name == "__init__"
                )
                paras.pop("", None)
                if paras:
                    docs[node.name] = "\n\n".join(paras)
    return docs


def _fix_initialization_sections(content: str) -> str:
    """Drop empty Initialization headings; inject docstrings autodoc2 dropped."""
    content = re.sub(r"(?m)^### Initialization\n\n(?=#{3,4} )", "", content)
    docs = _init_docstrings_by_class()

    def inject(m: re.Match[str]) -> str:
        block, cls = m.group(1), m.group(2)
        if cls not in docs or "### Initialization" in block:
            return block
        section = f"### Initialization\n\n{docs[cls]}\n\n"
        first = _MEMBER_HEADING_RE.search(block, block.index("\n") + 1)
        if not first:
            return f"{block}\n{section}"
        return block[: first.start()] + section + block[first.start() :]

    return _CLASS_BLOCK_RE.sub(inject, content)


# Attribute heading followed by a standalone literal-default line (``Ellipsis``
# for ``= ...``, ``None`` for ``= None``, etc.) emitted by autoapi.
_ATTR_HEADING_WITH_DEFAULT_RE = re.compile(
    r"^(?P<hashes>#{3,4}) (?P<name>[\w.]+) (?P<annot>\*: (?P<type>[^\n]+?)\*)[ \t]*\n\n"
    r"(?:Ellipsis|None|True|False)\n",
    re.MULTILINE,
)
# Private Protocol class names (e.g. ``_ABICallProtocolType``).
_PROTOCOL_TYPE_RE = re.compile(r"^_\w+Protocol(?:Type)?$")


def _simplify_attribute_renderings(content: str) -> str:
    """Drop the noise autoapi emits for ``name: T = <literal>`` attributes.

    Always strips the standalone default-value line (``Ellipsis``/``None``/etc.).
    When ``T`` is a private Protocol class, also strips ``*: T*`` from the
    heading and remaps in-page anchors from the autodoc2 slug of the original
    heading to the github-slugger slug of the simplified one.
    """
    slug_remap: dict[str, str] = {}
    dropped_names: list[str] = []

    def sub(m: re.Match[str]) -> str:
        hashes = m.group("hashes")
        name = m.group("name")
        annot = m.group("annot")
        type_str = m.group("type")
        if _PROTOCOL_TYPE_RE.match(type_str):
            # Detect whether real content follows the ``Ellipsis`` line. If
            # the next non-blank text is another heading (or end-of-doc), the
            # attribute has no body and we drop the heading entirely. If
            # there's prose/code, this is a PEP 224-style documented
            # attribute (see ``arc4.pyi`` ``abi_call``) — keep a simplified
            # heading so the docstring stays attached to its name.
            tail = m.string[m.end():]
            tail_stripped = tail.lstrip("\n")
            has_body = bool(tail_stripped) and not tail_stripped.lstrip().startswith(("#", "</div>"))
            if not has_body:
                dropped_names.append(name)
                return ""
            original_heading = f"{name} {annot}"
            slug_remap[_compute_starlight_anchor(original_heading)] = _github_slug(name)
            return f"{hashes} {name}\n"
        return f"{hashes} {name} {annot}\n"

    new_content = _ATTR_HEADING_WITH_DEFAULT_RE.sub(sub, content)

    if slug_remap:
        def fix_anchor(m: re.Match[str]) -> str:
            return f"(#{slug_remap.get(m.group(1), m.group(1))})"
        new_content = re.sub(r"\(#([^)]+)\)", fix_anchor, new_content)

    if dropped_names:
        new_content = _strip_summary_rows(new_content, dropped_names)
    return new_content


def _strip_summary_rows(content: str, names: list[str]) -> str:
    """Remove summary-table rows whose link text matches any of ``names``.

    Also drops the section heading (``### Data``) and table-header separator
    row if the table is left empty.
    """
    for name in names:
        # Row form: ``| [`name`](#anchor) | description |``
        row_re = re.compile(
            rf"^\|\s*\[`{re.escape(name)}`\]\([^)]*\)\s*\|[^\n]*\n",
            re.MULTILINE,
        )
        content = row_re.sub("", content)
    # Drop ``### <heading>`` blocks whose body is only the now-empty
    # ``|---|---|`` separator row and surrounding blank lines.
    content = re.sub(
        r"^### \w+[ \t]*\n+\|[-| \t]+\|[ \t]*\n+(?=#|\Z)",
        "",
        content,
        flags=re.MULTILINE,
    )
    return content


def _build_anchor_map(content: str) -> dict[str, str]:
    anchor_map: dict[str, str] = {}
    for m in _H3_TEXT_RE.finditer(content):
        heading_text = m.group(1)
        key_m = re.match(r"(?:\*\w+\*\s+)?(\w+)", heading_text)
        if key_m:
            anchor_map[key_m.group(1)] = _github_slug(heading_text)
    return anchor_map


def _fix_qualified_anchors(
    content: str, path: Path, file_maps: dict[str, dict[str, str]]
) -> str:
    """Rewrite Sphinx-style qualified anchors to match Starlight heading IDs.

    Sphinx generates links like [Foo](#algopy.arc4.Foo) but Starlight generates
    anchors from rendered heading text (e.g. #class-foo for '### *class* Foo').
    """

    def fix_anchor(m: re.Match) -> str:
        path_part, symbol = m.group(1), m.group(2)
        if path_part:
            resolved = (path.parent / path_part).resolve()
            # autodoc2 links to sibling .md files directly; old autoapi linked to dirs
            target_md = resolved if path_part.endswith(".md") else resolved / "index.md"
        else:
            target_md = path
        anchor = file_maps.get(str(target_md), {}).get(symbol, symbol.lower())
        return f"({path_part}#{anchor})"

    return _QUALIFIED_ANCHOR_RE.sub(fix_anchor, content)


_ADMONITION_HEADING_RE = re.compile(
    r"^#### (NOTE|WARNING|TIP|IMPORTANT|CAUTION|DANGER|HINT|ATTENTION|SEEALSO)\s*$"
)
# Map rST admonition names to Starlight's four built-in asides.
_STARLIGHT_ADMONITION = {
    "note": "note",
    "hint": "tip",
    "tip": "tip",
    "warning": "caution",
    "caution": "caution",
    "attention": "caution",
    "important": "danger",
    "danger": "danger",
    "seealso": "note",
}


def _convert_admonitions(content: str) -> str:
    """Rewrite sphinx admonition headings as Starlight aside directives.

    sphinx-markdown-builder renders ``.. note::`` as ``#### NOTE`` followed by
    the body until the next heading. Starlight uses container directives
    (``:::note ... :::``), so we collect each admonition block and re-emit it.
    """
    lines = content.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _ADMONITION_HEADING_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        kind = _STARLIGHT_ADMONITION.get(m.group(1).lower(), "note")
        i += 1
        body: list[str] = []
        while i < n and not lines[i].lstrip().startswith("#"):
            body.append(lines[i])
            i += 1
        while body and body[-1].strip() == "":
            body.pop()
        while body and body[0].strip() == "":
            body.pop(0)
        out.append(f":::{kind}")
        out.extend(body)
        out.append(":::")
        out.append("")
    return "\n".join(out) + "\n" if out and content.endswith("\n") else "\n".join(out)


_PARAM_BULLET_RE = re.compile(r"^(\s{4,})\\\*(\s)", re.MULTILINE)
# Bare ``**name:**`` lines at column 0 — Sphinx strips the trailing double-space
# hard breaks the stub authors used, so these run together in the rendered output.
_BOLD_LABEL_LINE_RE = re.compile(r"^(\*\*\w+:\*\* )", re.MULTILINE)


def _bullet_bold_label_lines(content: str) -> str:
    """Turn ``**name:** ...`` lines into list items so each renders on its own line."""
    return _BOLD_LABEL_LINE_RE.sub(r"- \1", content)


# A lone ``:param:`` renders as an indented continuation of ``* **Parameters:**``
# (``  **name** – desc``) with no bullet of its own, so it collapses onto the
# Parameters line. Multi-param blocks already get nested bullets; give the lone
# case one too so it renders on its own line.
_LONE_PARAM_RE = re.compile(r"(?m)^( {2,})(\*\*[^*\n]+\*\* –)")


def _fix_lone_param_bullet(content: str) -> str:
    return _LONE_PARAM_RE.sub(r"\1* \2", content)


def _fix_param_bullet_escapes(content: str) -> str:
    """Unescape ``\\*`` sub-bullets that appear inside Parameter blocks.

    Sphinx already renders ``:param:`` field lists into a Parameters bullet
    structure, but ``*`` characters used by docstring authors as nested bullets
    are emitted as ``\\*`` and stay as literal text. They sit at 4-space indent
    inside the parameter item, which is exactly the depth a real nested bullet
    needs — so dropping the backslash turns them into proper nested bullets.
    """
    return _PARAM_BULLET_RE.sub(r"\1*\2", content)


def _fix_member_index_anchors(content: str) -> str:
    """Fix member-index table anchor links to use github-slugger slugs.

    autodoc2 generates a member-index table at the top of each API page with links
    like [`addw`](#addw-a-uint64-int-...) that use its own slug algorithm. Starlight
    renders heading IDs using github-slugger which produces different slugs
    (e.g. #addwa-uint64--int-... for the same heading). This function rebuilds the
    mapping from every ### heading's autodoc2 slug → github-slugger slug and rewrites
    all (#...) same-page anchor references in each file.
    """
    slug_map: dict[str, str] = {}
    for m in _H3_TEXT_RE.finditer(content):
        heading_text = m.group(1)
        old_slug = _compute_starlight_anchor(heading_text)
        new_slug = _github_slug(heading_text)
        if old_slug != new_slug:
            slug_map[old_slug] = new_slug

    if not slug_map:
        return content

    def fix_anchor(m: re.Match) -> str:
        anchor = m.group(1)
        return f"(#{slug_map.get(anchor, anchor)})"

    return re.sub(r"\(#([^)]+)\)", fix_anchor, content)


def _process_md_files() -> None:
    """Read raw markdown from SPHINX_OUT, transform in memory, atomically write to API_OUT.

    Reads every .md from the sphinx scratch dir, runs each post-processing
    step against the cached content, and finally writes each file once into
    ``src/content/docs/api/`` using ``os.replace`` so the dev server's watcher
    only sees finished files (not partial sphinx output, no per-step rewrites).
    """
    print("==> Post-processing API markdown...")
    sphinx_files: dict[Path, str] = {
        p: p.read_text(encoding="utf-8") for p in sorted(SPHINX_OUT.rglob("*.md"))
    }
    # Final-destination paths keyed for use in the cross-file anchor map.
    files: dict[Path, str] = {
        API_OUT / p.relative_to(SPHINX_OUT): content
        for p, content in sphinx_files.items()
    }

    # Per-file transforms (no cross-file dependencies).
    for path in files:
        content = files[path]
        content = _inject_frontmatter(path, content)
        content = _convert_admonitions(content)
        content = _fix_summary_table_headers(content)
        content = _fix_param_bullet_escapes(content)
        content = _bullet_bold_label_lines(content)
        content = _fix_lone_param_bullet(content)
        content = _strip_default_language(content)
        content = _collapse_nested_links(content)
        content = _shorten_qualified_names(content)
        content = _simplify_class_headings(content)
        content = _qualify_method_headings(content)
        content = _fix_initialization_sections(content)
        content = _split_function_signatures(content)
        content = _simplify_attribute_renderings(content)
        content = _fix_module_md_links(content)
        content = _fix_member_index_anchors(content)
        files[path] = content

    # Cross-file anchor map (built after heading transforms have settled).
    file_maps = {str(p): _build_anchor_map(c) for p, c in files.items()}
    for path, content in files.items():
        files[path] = _fix_qualified_anchors(content, path, file_maps)

    # Atomic write per file: write to a tmp sibling and os.replace onto the
    # final path. Astro's watcher then only sees complete files.
    expected: set[Path] = set()
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
        expected.add(path.resolve())
    # Drop any stale .md files left over from a previous build.
    for stale in API_OUT.rglob("*.md"):
        if stale.resolve() not in expected:
            stale.unlink()


# Main --------------------------------------------------------------------------


def main() -> None:
    """Run the full API docs build pipeline."""
    _generate_stubs()
    _preprocess_docstrings()
    _clean_sphinx_out()
    _run_sphinx_build()
    _remove_sphinx_artifacts()
    _flatten_autoapi()
    _process_md_files()

    file_count = sum(1 for _ in API_OUT.rglob("*.md"))
    print(f"==> API docs generated at: {API_OUT}")
    print(f"    {file_count} markdown files")


if __name__ == "__main__":
    main()