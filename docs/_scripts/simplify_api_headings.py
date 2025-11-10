#!/usr/bin/env python3
"""
Post-process generated API markdown to simplify headings.

This script modifies API documentation markdown files to have shorter,
more TOC-friendly headings by extracting just the function/method name
and moving the full signature below the heading.
"""

import re
import sys
from pathlib import Path


def simplify_heading(match: re.Match) -> str:
    """Simplify an API heading by extracting just the name."""
    full_heading = match.group(0)
    # Extract the function/method name (everything before the first '(')
    heading_line = match.group(1)

    # Find the function name (last part before parenthesis or first word after ###)
    name_match = re.match(r'###\s+([^\(]+)', heading_line)
    if not name_match:
        return full_heading  # Can't parse, return unchanged

    name = name_match.group(1).strip()

    # Extract the full signature (everything after the name)
    sig_match = re.search(r'(\([^→]+(→[^)]+)?.*?)$', heading_line)
    if not sig_match:
        return full_heading  # No signature found, return unchanged

    signature = sig_match.group(1).strip()

    # Return simplified heading with full signature including full member name in italics
    return f"### {name}\n\n*{name}{signature}*"


def process_markdown_file(file_path: Path) -> bool:
    """Process a single markdown file to simplify API headings."""
    try:
        content = file_path.read_text(encoding='utf-8')

        # Pattern to match API headings (### with parentheses and complex signatures)
        # Matches headings that have function signatures (contain parentheses)
        pattern = r'^(###\s+\S+.*?\(.*?\)[^\n]*?)$'

        # Replace long headings
        new_content = re.sub(
            pattern,
            simplify_heading,
            content,
            flags=re.MULTILINE
        )

        # Only write if content changed
        if new_content != content:
            file_path.write_text(new_content, encoding='utf-8')
            return True
        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Process all API markdown files in the build directory."""
    # Get the markdown build directory
    docs_dir = Path(__file__).parent.parent
    markdown_dir = docs_dir / "_build" / "markdown"

    if not markdown_dir.exists():
        print(f"Markdown directory not found: {markdown_dir}", file=sys.stderr)
        sys.exit(1)

    # Process all api-*.md files
    api_files = list(markdown_dir.glob("api-*.md")) + [markdown_dir / "api.md"]

    processed = 0
    for file_path in api_files:
        if file_path.exists():
            if process_markdown_file(file_path):
                processed += 1
                print(f"Processed: {file_path.name}")

    print(f"\nSimplified headings in {processed} files")


if __name__ == "__main__":
    main()
