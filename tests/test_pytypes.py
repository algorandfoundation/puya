import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from puyapy.awst_build import pytypes
from tests import STUBS_DIR


def _module_name_from_path(file_path: Path, stubs_root: Path) -> str:
    if file_path.stem == "__init__":
        mod_path = file_path.parent
    else:
        mod_path = file_path.with_suffix("")
    rel = mod_path.relative_to(stubs_root)
    parts = list(rel.parts)
    parts[0] = parts[0].removesuffix("-stubs")
    return ".".join(parts)


def _symbols_from_file(file_path: Path) -> list[str]:
    """
    Parse a single .pyi file and return class names,
    and module level assignments which are (probably) type annotations.
    """
    text = file_path.read_text(encoding="utf8")
    tree = ast.parse(text, filename=str(file_path))
    symbols = []
    for stmt in tree.body:
        match stmt:
            case ast.ClassDef(name=class_name):
                symbols.append(class_name)
            case (
                ast.AnnAssign(target=ast.Name(id=alias_name))
                | ast.Assign(targets=[ast.Name(id=alias_name)])
            ) if stmt.value is None or not _is_ellipsis(stmt.value):
                symbols.append(alias_name)
    return symbols


def _is_ellipsis(expr: ast.expr) -> bool:
    match expr:
        case ast.Constant(value=value):
            return value is Ellipsis
        case _:
            return False


def _stub_class_names_and_predefined_aliases() -> list[str]:
    stubs_root = STUBS_DIR.parent.resolve()
    results = []
    for path in stubs_root.rglob("*.pyi"):
        module = _module_name_from_path(path, stubs_root)
        symbols = _symbols_from_file(path)
        qualified_symbols = [f"{module}.{name}" for name in symbols if not name.startswith("_")]
        results.extend(qualified_symbols)
    return results


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


@pytest.mark.parametrize("fullname", _stub_class_names_and_predefined_aliases(), ids=str)
def test_stub_class_names_lookup(
    builtins_registry: Mapping[str, pytypes.PyType], fullname: str
) -> None:
    assert fullname in builtins_registry, f"{fullname} is missing from pytypes"
