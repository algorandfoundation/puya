import ast
import inspect
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple

from prettytable import PrettyTable

# TODO: update to follow the new project structure

PROJECT_ROOT = (Path(__file__).parent / "..").resolve()
VCS_ROOT = (PROJECT_ROOT / "..").resolve()
STUBS = VCS_ROOT / "stubs" / "algopy-stubs"
IMPL = PROJECT_ROOT / "src"
ROOT_MODULE = "algopy"


class ASTNodeDefinition(NamedTuple):
    node: ast.AST
    path: Path
    name: str
    object_type: str


class CoverageResult(NamedTuple):
    full_name: str
    impl_file: str | None
    stub_file: str
    coverage: float
    missing: str


class ImplCoverage:
    def __init__(
        self, path: Path, defined: list[str] | None = None, missing: list[str] | None = None
    ):
        self.path = path
        self.defined = defined or []
        self.missing = missing or []

    @property
    def coverage(self) -> float:
        if not self.defined:
            return 1
        total = len(self.defined)
        implemented = total - len(self.missing)
        return implemented / total


def main() -> None:
    stubs = collect_public_stubs()
    coverage = collect_coverage(stubs)
    print_results(coverage)


def collect_public_stubs() -> dict[str, ASTNodeDefinition]:
    stubs_root = STUBS / "__init__.pyi"
    stubs_ast = _parse_python_file(stubs_root)
    result = dict[str, ASTNodeDefinition]()
    for stmt in stubs_ast.body:
        if isinstance(stmt, ast.ImportFrom):
            if stmt.module is None:
                raise NotImplementedError
            for name in stmt.names:
                if isinstance(name, ast.alias):
                    result.update(collect_imports(stmt, name))
                else:
                    raise NotImplementedError
    return result


def collect_imports(
    stmt: ast.ImportFrom, alias: ast.alias
) -> Iterable[tuple[str, ASTNodeDefinition]]:
    assert stmt.module is not None
    # remove algopy.
    relative_module = stmt.module.split(".", maxsplit=1)[-1]
    src = alias.name
    dest = alias.asname
    # from module import *
    if src == "*" and dest is None:
        for defn_name, defn in collect_stubs(STUBS, relative_module).items():
            yield f"{ROOT_MODULE}.{defn_name}", defn
    # from root import src as src
    elif stmt.module == ROOT_MODULE and dest == src:
        for defn_name, defn in collect_stubs(STUBS, src).items():
            yield f"{ROOT_MODULE}.{dest}.{defn_name}", defn
    # from foo.bar import src as src
    elif dest == src:
        stubs = collect_stubs(STUBS, relative_module)
        yield f"{ROOT_MODULE}.{src}", stubs[src]
    else:
        raise NotImplementedError


def collect_stubs(stubs_dir: Path, relative_module: str) -> dict[str, ASTNodeDefinition]:
    if "." in relative_module:
        raise NotImplementedError("Nested modules not implemented")
    module_path = (stubs_dir / relative_module).with_suffix(".pyi")
    stubs_ast = _parse_python_file(module_path)
    result = dict[str, ASTNodeDefinition]()
    for stmt in stubs_ast.body:
        name = ""
        node_type = ""
        node: ast.AST | None = None
        match stmt:
            case ast.ClassDef(name=name) as node:
                node_type = "Class"
            case ast.FunctionDef(name=name) as node:
                node_type = "Function"
            case ast.Assign(targets=[ast.Name(id=name)], value=node) | ast.AnnAssign(
                target=ast.Name(id=name), value=node
            ):
                node_type = type(node).__name__
        if node and not name.startswith("_"):
            result[name] = ASTNodeDefinition(node, module_path, name, node_type)
    return result


def collect_coverage(stubs: dict[str, ASTNodeDefinition]) -> list[CoverageResult]:
    result = []
    for full_name, stub in stubs.items():
        if "op.pyi" in str(stub.path):
            print("stop")

        coverage = _get_impl_coverage(full_name, stub)
        result.append(
            CoverageResult(
                full_name=full_name,
                stub_file=str(stub.path.relative_to(STUBS)),
                impl_file=str(coverage.path.relative_to(IMPL)) if coverage else "",
                coverage=coverage.coverage if coverage else 0,
                missing=", ".join(coverage.missing if coverage else []),
            )
        )
    return result


def print_results(results: list[CoverageResult]) -> None:
    table = PrettyTable(
        field_names=["Name", "Implementation", "Source Stub", "Coverage", "Missing"],
        sortby="Coverage",
        header=True,
        border=True,
        padding_width=2,
        reversesort=True,
        left_padding_width=0,
        right_padding_width=1,
        align="l",
        max_width=100,
    )

    for result in results:
        table.add_row(
            [
                result.full_name,
                result.impl_file,
                result.stub_file,
                f"{result.coverage:.2%}",
                result.missing,
            ],
            divider=True,
        )

    print(table)


def _parse_python_file(filepath: Path) -> ast.Module:
    """Parse a Python file and return its AST."""
    with filepath.open() as file:
        tree = ast.parse(file.read(), filename=str(filepath))
    return tree


def _get_impl_coverage(symbol: str, stub: ASTNodeDefinition) -> ImplCoverage | None:
    import importlib

    module, name = symbol.rsplit(".", maxsplit=1)
    try:
        mod = importlib.import_module(module)
    except ImportError:
        return None
    try:
        impl = getattr(mod, name)
    except AttributeError:
        return None

    try:
        impl_path = Path(inspect.getfile(impl))
    except Exception as e:
        print(e)
        return None
    return _compare_stub_impl(stub.node, impl, impl_path)


def _compare_stub_impl(stub: ast.AST, impl: object, impl_path: Path) -> ImplCoverage:
    # classes are really the only types that can be "partially implemented"
    # from a typing perspective
    if not isinstance(stub, ast.ClassDef):
        return ImplCoverage(impl_path)

    # using vars to only get explicitly implemented members
    # need more sophisticated approach if implementations start using inheritance
    impl_members = set(vars(impl))
    stub_members = set()
    for stmt in stub.body:
        # TODO: class vars?
        if isinstance(stmt, ast.FunctionDef):
            stub_members.add(stmt.name)

    if not stub_members:  # no members?
        return ImplCoverage(impl_path)

    # exclude some default implementations
    default_impls = {
        f"__{op}__"
        for op in (
            "ipow",
            "imod",
            "ifloordiv",
            "irshift",
            "ilshift",
            "ior",
            "iand",
            "iadd",
            "ixor",
            "imul",
            "isub",
            "ne",
        )
    }
    missing = sorted(stub_members.difference({*impl_members, *default_impls}))
    return ImplCoverage(impl_path, sorted(stub_members), missing)


if __name__ == "__main__":
    main()
