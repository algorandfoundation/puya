#!/usr/bin/env python3
"""
Post-process generated API markdown files.

This script performs two transformations on sphinx-markdown-builder output:

1. Fix heading hierarchy: sphinx-markdown-builder has hardcoded heading levels
   that create broken hierarchy where classes and section headers are at the
   same level. We fix this by shifting API section content down one level.

2. Simplify headings: Extract function/method names from long signature headings
   to make TOCs more readable, moving the full signature into the content.

Combined processing ensures both fixes work together correctly.
"""
import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
MARKDOWN_BUILD_DIR = DOCS_DIR / "_build" / "markdown"


def fix_heading_hierarchy(content: str) -> str:
    """
    Fix heading hierarchy in API markdown files.

    In the "### API" section:
    - Convert h3 class/function headings (### *class*) to h4
    - Convert h3 subsection headings (### Initialization) to h5
    - Convert h4 method/property headings to h5

    This creates proper nesting:
        ## Package Contents (h2)
        ### API (h3)
        #### *class* Foo (h4) ← Class definition
        ##### Initialization (h5) ← Subsection
        ##### method() (h5) ← Methods at same level as subsections
    """
    lines = content.split("\n")
    result = []
    in_api_section = False

    for line in lines:
        # Detect when we enter the API section
        if line.strip() == "### API":
            in_api_section = True
            result.append(line)
            continue

        # Detect when we exit the API section (reach next h2)
        if in_api_section and re.match(r"^##\s+(?!#)", line):
            in_api_section = False

        if not in_api_section:
            result.append(line)
            continue

        # In API section: adjust heading levels based on content
        if line.startswith("### "):
            # Check if this is a class/function definition or a subsection
            if re.match(r"^###\s+\*(?:class|function)\*", line):
                # This is a class or function definition: h3 → h4
                result.append(line.replace("### ", "#### ", 1))
            else:
                # This is a subsection (like "Initialization"): h3 → h5
                result.append(line.replace("### ", "##### ", 1))
        elif line.startswith("#### "):
            # Methods/properties: h4 → h5
            result.append(line.replace("#### ", "##### ", 1))
        else:
            result.append(line)

    return "\n".join(result)


def simplify_heading(match: re.Match) -> str:
    """
    Simplify an API heading by extracting just the name.

    Transforms:
        #### method_name(arg1: Type1, arg2: Type2) → ReturnType

    Into:
        #### method_name

        *method_name(arg1: Type1, arg2: Type2) → ReturnType*
    """
    full_heading = match.group(0)
    heading_line = match.group(1)
    heading_level = match.group(2)  # The heading level markers (####, #####, etc.)

    # Extract the name (everything before the first '(')
    name_match = re.match(rf'{re.escape(heading_level)}\s+([^\(]+)', heading_line)
    if not name_match:
        return full_heading  # Can't parse, return unchanged

    name = name_match.group(1).strip()

    # Extract the full signature (everything after the name, including parentheses)
    sig_match = re.search(r'(\([^→]+(→.*)?)$', heading_line)
    if not sig_match:
        return full_heading  # No signature found, return unchanged

    signature = sig_match.group(1).strip()

    # Return simplified heading with full signature in italics below
    return f"{heading_level} {name}\n\n*{name}{signature}*"


def simplify_headings(content: str) -> str:
    """
    Simplify API headings to make TOCs more readable.

    Extracts method/function names from complex signatures and moves
    the full signature into the content below the heading.

    Applies to h4, h5, h6 headings (####, #####, ######) that contain
    function/method signatures (parentheses).
    """
    # Pattern to match headings at h4+ level with function signatures
    # Matches headings that contain parentheses (function/method signatures)
    pattern = r'^((#{4,6})\s+\S+.*?\(.*?\)[^\n]*?)$'

    return re.sub(
        pattern,
        simplify_heading,
        content,
        flags=re.MULTILINE
    )


def process_api_file(file_path: Path) -> bool:
    """
    Process a single API markdown file with both transformations.

    Returns True if the file was modified, False otherwise.
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content

        # Apply transformations in order:
        # 1. Fix heading hierarchy first
        content = fix_heading_hierarchy(content)
        # 2. Then simplify the (now correctly-leveled) headings
        content = simplify_headings(content)

        # Only write if content changed
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        return False

    except Exception as e:
        print(f"❌ Error processing {file_path.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    """Process all API markdown files in the build directory."""
    if not MARKDOWN_BUILD_DIR.exists():
        print(f"❌ Markdown build directory not found: {MARKDOWN_BUILD_DIR}", file=sys.stderr)
        return 1

    # Find all API documentation files
    api_files = sorted(MARKDOWN_BUILD_DIR.glob("api*.md"))

    if not api_files:
        print(f"⚠️  No API markdown files found in {MARKDOWN_BUILD_DIR}", file=sys.stderr)
        return 0

    print(f"\n📝 Post-processing {len(api_files)} API markdown files...")
    modified_count = 0

    for file_path in api_files:
        if process_api_file(file_path):
            print(f"   ✓ {file_path.name}")
            modified_count += 1
        else:
            print(f"   - {file_path.name} (no changes needed)")

    print(f"\n✅ Modified {modified_count} of {len(api_files)} files\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
