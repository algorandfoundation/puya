#!/usr/bin/env python3
"""Generate API reference markdown from algopy stubs, then post-process for Starlight.

Pipeline:
  1. Run scripts/generate_docs.output_doc_stubs() to produce processed .pyi files
     in docs/algopy-stubs/ (reuses the existing mypy-based stub processing).
  2. Run sphinx-build -b markdown against docs/sphinx/ to generate raw markdown.
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

import re
import shutil
import subprocess
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
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
    r"(?<!\[)(?<!#)(?<!/)(?<!\.md)"
    r"(?:" + _pkg + r"|typing_extensions|collections\.abc)"
    r"(?:\.\w+)*\.(\w+)"
)

_INDEX_MD_RE = re.compile(r"/index\.md")

# Matches *class* headings with constructor signatures:
# "### *class* Foo(\*args, \*\*kwds)"
_CLASS_ARGS_RE = re.compile(
    r"^(#{3,4} \*class\* \w+)\(.*\)\s*$",
    re.MULTILINE,
)

_H3_TEXT_RE = re.compile(r"^### (.+)$", re.MULTILINE)

_QUALIFIED_ANCHOR_RE = re.compile(
    r"\(([^()\s\"']*?)#(?:" + _pkg + r"|typing_extensions|collections\.abc)"
    r"(?:\.\w+)*\.(\w+)\)"
)


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


# Step 2: Sphinx markdown build -------------------------------------------------


def _clean_api_output() -> None:
    print("==> Cleaning previous API output...")
    if API_OUT.exists():
        shutil.rmtree(API_OUT)
    API_OUT.mkdir(parents=True, exist_ok=True)


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
            str(API_OUT),
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


# Step 3: post-processing -------------------------------------------------------


def _remove_sphinx_artifacts() -> None:
    print("==> Removing Sphinx artifacts...")
    for name in [".buildinfo"]:
        p = API_OUT / name
        if p.exists():
            p.unlink()
    doctrees = API_OUT / ".doctrees"
    if doctrees.exists():
        shutil.rmtree(doctrees)
    # Remove the top-level index.md generated from index.rst (not needed in Starlight)
    index_md = API_OUT / "index.md"
    if index_md.exists():
        index_md.unlink()


def _flatten_autodoc2() -> None:
    """Move autoapi/<package>/ up one level to api/<package>/."""
    print("==> Flattening autodoc2 directory structure...")
    autodoc2_pkg = API_OUT / "autoapi" / PACKAGE_NAME
    target = API_OUT / PACKAGE_NAME

    if not autodoc2_pkg.is_dir():
        print(
            f"WARNING: Expected autodoc2 directory not found: {autodoc2_pkg}\n"
            "         The output may already be flat, or conf.py needs adjustment.",
            file=sys.stderr,
        )
        return

    if target.exists():
        shutil.rmtree(target)
    shutil.move(str(autodoc2_pkg), str(target))

    autoapi_dir = API_OUT / "autoapi"
    if autoapi_dir.exists():
        shutil.rmtree(autoapi_dir)


def _extract_title(file_path: Path) -> str:
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("# "):
                return line[2:].strip()
    return file_path.stem


def _inject_frontmatter() -> None:
    print("==> Injecting Starlight frontmatter into API docs...")
    for md_file in sorted(API_OUT.rglob("*.md")):
        title = _extract_title(md_file)
        escaped = title.replace('"', '\\"')
        content = md_file.read_text(encoding="utf-8")
        # Strip the H1 — Starlight renders title from frontmatter.
        content = re.sub(r"^# [^\n]*\n+", "", content)
        md_file.write_text(
            f'---\ntitle: "{escaped}"\n---\n\n<div class="api-ref">\n\n{content}\n\n</div>\n',
            encoding="utf-8",
        )


def _fix_internal_links() -> None:
    """Strip /index.md from internal link paths — Starlight doesn't use extensions."""
    print("==> Fixing internal links...")
    for md_file in sorted(API_OUT.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        updated = _INDEX_MD_RE.sub("/", content)
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")


def _shorten_qualified_names() -> None:
    """Strip module prefixes from H3/H4 headings (e.g. algopy.arc4.Address → Address)."""
    print("==> Shortening qualified names in headings...")
    for md_file in sorted(API_OUT.rglob("*.md")):
        lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            if not _HEADING_RE.match(line):
                continue
            new_line = _LINKED_QUALIFIED_RE.sub(r"[\1]", line)
            new_line = _PLAIN_QUALIFIED_RE.sub(r"\1", new_line)
            if new_line != line:
                lines[i] = new_line
                changed = True
        if changed:
            md_file.write_text("".join(lines), encoding="utf-8")


def _compute_starlight_anchor(heading_text: str) -> str:
    """Compute the anchor slug that Starlight/rehype-slug generates from heading text."""
    text = re.sub(r"\*([^*]+)\*", r"\1", heading_text)   # *em* → em
    text = re.sub(r"`([^`]+)`", r"\1", text)              # `code` → code
    text = re.sub(r"\\.", "", text)                        # \* → (removed)
    text = text.lower()
    text = re.sub(r"[^a-z0-9-]+", " ", text)
    return "-".join(text.split())


def _simplify_class_headings() -> None:
    """Strip constructor signatures from *class* headings for predictable anchors.

    Converts: ### *class* Foo(\\*args, \\*\\*kwds)
    To:        ### *class* Foo

    Without this, Starlight generates messy anchors like #class-foo-args--kwds
    that don't match the plain #class-foo used in summary table links.
    """
    print("==> Simplifying class heading signatures...")
    for md_file in sorted(API_OUT.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        updated = _CLASS_ARGS_RE.sub(r"\1", content)
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")


def _fix_qualified_anchors() -> None:
    """Rewrite Sphinx-style qualified anchors to match Starlight heading IDs.

    Sphinx generates links like [Foo](#algopy.arc4.Foo) but Starlight generates
    anchors from rendered heading text (e.g. #class-foo for '### *class* Foo').
    """
    print("==> Fixing qualified name anchors...")
    file_maps: dict[str, dict[str, str]] = {}
    for md_file in sorted(API_OUT.rglob("*.md")):
        anchor_map: dict[str, str] = {}
        content = md_file.read_text(encoding="utf-8")
        for m in _H3_TEXT_RE.finditer(content):
            heading_text = m.group(1)
            key_m = re.match(r"(?:\*\w+\*\s+)?(\w+)", heading_text)
            if key_m:
                symbol = key_m.group(1)
                anchor_map[symbol] = _compute_starlight_anchor(heading_text)
        file_maps[str(md_file)] = anchor_map

    for md_file in sorted(API_OUT.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")

        def fix_anchor(m: re.Match, _file: Path = md_file) -> str:
            path_part, symbol = m.group(1), m.group(2)
            if path_part:
                target_md = (_file.parent / path_part).resolve() / "index.md"
            else:
                target_md = _file
            anchor = file_maps.get(str(target_md), {}).get(symbol, symbol.lower())
            return f"({path_part}#{anchor})"

        updated = _QUALIFIED_ANCHOR_RE.sub(fix_anchor, content)
        if updated != content:
            md_file.write_text(updated, encoding="utf-8")


# Main --------------------------------------------------------------------------


def main() -> None:
    """Run the full API docs build pipeline."""
    _generate_stubs()
    _clean_api_output()
    _run_sphinx_build()
    _remove_sphinx_artifacts()
    _flatten_autodoc2()
    _inject_frontmatter()
    _fix_internal_links()
    _shorten_qualified_names()
    _simplify_class_headings()
    _fix_qualified_anchors()

    file_count = sum(1 for _ in API_OUT.rglob("*.md"))
    print(f"==> API docs generated at: {API_OUT}")
    print(f"    {file_count} markdown files")


if __name__ == "__main__":
    main()