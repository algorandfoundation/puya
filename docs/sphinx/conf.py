# Isolated Sphinx configuration for API-only markdown generation.
# This config is used by docs/api_build.py to generate API reference
# markdown that is consumed by Starlight.

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sphinx.application import Sphinx

from docutils import nodes

project = "Algorand Python"
copyright = "2024, Algorand Foundation"
author = "Algorand Foundation"

extensions = ["autoapi.extension"]

templates_path = []
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- AutoAPI configuration ---------------------------------------------------
# Points to the staging directory created by docs/api_build.py, which copies
# docs/algopy-stubs/ → docs/_autoapi_source/algopy/ so autoapi sees a valid
# Python package name ("algopy") rather than the hyphenated directory name.

autoapi_dirs = ["../_autoapi_source"]
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]


# -- pycon/doctest → python conversion hook ----------------------------------
# Starlight's Expressive Code doesn't support the "pycon" or "doctest" lexers.
# This hook converts those code blocks to plain Python and strips REPL prompts
# so syntax highlighting works correctly.


def _strip_pycon_prompts(text: str) -> str:
    """Return text with leading REPL prompts (>>>/...) stripped from each line."""
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith(">>> "):
            cleaned_lines.append(line[4:])
            continue
        if line.startswith(">>>"):
            cleaned_lines.append(line[3:].lstrip())
            continue
        if line.startswith("... "):
            cleaned_lines.append(line[4:])
            continue
        if line.startswith("..."):
            cleaned_lines.append(line[3:].lstrip())
            continue
        if line.startswith("\u2026 "):  # typographic ellipsis
            cleaned_lines.append(line[2:])
            continue
        if line.startswith("\u2026"):
            cleaned_lines.append(line[1:].lstrip())
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def convert_pycon_blocks_to_python(app: "Sphinx", doctree: object, docname: str) -> None:
    """Convert pycon/doctest code blocks to python and strip prompts for Markdown."""
    if app.builder.name != "markdown":
        return

    for node in list(doctree.traverse(nodes.literal_block)):  # type: ignore[attr-defined]
        language = node.get("language")
        if language in {"pycon", "doctest"}:
            text = node.astext()
            node["language"] = "python"
            node.children = [nodes.Text(_strip_pycon_prompts(text))]

    doctest_block = getattr(nodes, "doctest_block", None)
    if doctest_block is not None:
        for node in list(doctree.traverse(doctest_block)):  # type: ignore[attr-defined]
            text = node.astext()
            code_text = _strip_pycon_prompts(text)
            replacement = nodes.literal_block(code_text, code_text)
            replacement["language"] = "python"
            node.replace_self(replacement)

    for field in doctree.traverse(nodes.field):  # type: ignore[attr-defined]
        if len(field) < 2 or not isinstance(field[0], nodes.field_name):
            continue
        field_name_text = field[0].astext().strip().lower()
        if field_name_text not in {"example", "examples"}:
            continue
        field_body = field[1]
        if not isinstance(field_body, nodes.field_body):
            continue
        for child in list(field_body.children):
            if not isinstance(child, (nodes.paragraph, nodes.block_quote)):
                continue
            text = child.astext()
            lines = text.splitlines()
            is_doctest = any(ln.strip().startswith((">>>", "...", "\u2026")) for ln in lines)
            if not is_doctest:
                continue
            code_text = _strip_pycon_prompts(text)
            replacement = nodes.literal_block(code_text, code_text)
            replacement["language"] = "python"
            child.replace_self(replacement)


def setup(app: "Sphinx") -> dict[str, object]:
    """Sphinx extension setup function."""
    app.connect("doctree-resolved", convert_pycon_blocks_to_python)
    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }