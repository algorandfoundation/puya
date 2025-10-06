import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from puyapy.awst_build import pytypes
from tests import VCS_ROOT


def module_name_from_path(file_path: Path, stubs_root: Path) -> str:
    rel = file_path.relative_to(stubs_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.pyi":
        mod_parts = parts[:-1]
    else:
        # strip .pyi suffix
        mod_parts = parts[:-1] + [parts[-1][:-4]]
    return ".".join(mod_parts)


def collect_from_file(file_path: Path) -> tuple[set[str], set[str]]:
    """Parse a single .pyi file and return (classes, aliases) sets of names."""
    text = file_path.read_text(encoding="utf8")
    try:
        tree = ast.parse(text, filename=str(file_path))
    except SyntaxError:
        # Some stub files may use syntax not supported by the running Python
        # interpreter (rare). Skip files we can't parse.
        return set(), set()

    classes: set[str] = set()
    aliases: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            classes.add(node.name)
        elif isinstance(node, ast.AnnAssign):
            # annotated assignment: name: TypeAlias = ...
            target = node.target
            if isinstance(target, ast.Name) and node.annotation is not None:
                ann = node.annotation
                ann_id = getattr(ann, "id", None) or getattr(ann, "attr", None)
                if ann_id == "TypeAlias":
                    aliases.add(target.id)

    return classes, aliases


def stub_class_names_and_predefined_aliases() -> list[str]:
    root_module = "algopy"
    stubs_root = (VCS_ROOT / "stubs" / "algopy-stubs").resolve()
    results: set[str] = set()
    for path in stubs_root.rglob("*.pyi"):
        # compute module name
        try:
            module = module_name_from_path(path, stubs_root)
        except Exception:
            continue
        classes, aliases = collect_from_file(path)
        for name in classes | aliases:
            if name.startswith("_"):
                continue
            if module:
                results.add(f"{root_module}.{module}.{name}")
            else:
                results.add(f"{root_module}.{name}")

    return sorted(results)


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


@pytest.mark.parametrize(
    "fullname",
    stub_class_names_and_predefined_aliases(),
    ids=str,
)
def test_stub_class_names_lookup(
    builtins_registry: Mapping[str, pytypes.PyType], fullname: str
) -> None:
    assert fullname in builtins_registry, f"{fullname} is missing from pytypes"
