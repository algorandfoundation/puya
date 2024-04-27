import ast
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from prettytable import PrettyTable


def get_python_files(directory: Path) -> Iterator[Path]:
    """Yield Python file paths in the given directory recursively."""
    for entry in directory.rglob("*.py"):
        yield entry
    for entry in directory.rglob("*.pyi"):
        yield entry


def parse_python_file(filepath: Path) -> ast.Module:
    """Parse a Python file and return its AST."""
    with filepath.open() as file:
        tree = ast.parse(file.read(), filename=str(filepath))
    return tree


class ASTNodeDefinition(NamedTuple):
    name: str
    object_type: str


def extract_definitions(tree: ast.Module) -> set[ASTNodeDefinition]:
    def get_node_type(node: ast.AST) -> str:
        if isinstance(node, ast.ClassDef):
            return "Class"
        elif isinstance(node, ast.FunctionDef):
            return "Function"
        return ""

    return {
        ASTNodeDefinition(node.name, get_node_type(node))
        for node in tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef)
    }


class CoverageResult(NamedTuple):
    abstraction_node: ASTNodeDefinition
    impl_file: str
    stub_file: str
    coverage: float


def compare_definitions(stubs_dir: Path, impl_dir: Path) -> list[CoverageResult]:
    results = []

    for stub_file in get_python_files(stubs_dir):
        stub_tree = parse_python_file(stub_file)
        stub_defs = extract_definitions(stub_tree)

        if stub_file.name.startswith("_") and stub_file.suffix == ".pyi":
            for impl_file, impl_defs in get_impl_defs(impl_dir, stub_defs):
                for stub_def in stub_defs:
                    coverage = calculate_coverage(stub_def, impl_defs)
                    results.append(
                        CoverageResult(
                            abstraction_node=stub_def,
                            impl_file=impl_file.name,
                            stub_file=stub_file.name,
                            coverage=coverage,
                        )
                    )
        else:
            impl_file = impl_dir / stub_file.with_suffix(".py").name
            impl_tree = parse_python_file(impl_file) if impl_file.exists() else None
            impl_defs = extract_definitions(impl_tree) if impl_tree else set()
            for stub_def in stub_defs:
                coverage = calculate_coverage(stub_def, impl_defs)
                results.append(
                    CoverageResult(
                        abstraction_node=stub_def,
                        impl_file=impl_file.name,
                        stub_file=stub_file.name,
                        coverage=coverage,
                    )
                )

    return results


def get_impl_defs(
    impl_dir: Path, stub_defs: set[ASTNodeDefinition]
) -> Iterator[tuple[Path, set[ASTNodeDefinition]]]:
    for impl_file in get_python_files(impl_dir):
        impl_tree = parse_python_file(impl_file)
        impl_defs = extract_definitions(impl_tree)
        if stub_defs & impl_defs:
            yield impl_file, impl_defs


def calculate_coverage(stub_def: ASTNodeDefinition, impl_defs: set[ASTNodeDefinition]) -> float:
    if stub_def not in impl_defs:
        return 0.0
    # TODO: extend to outline actual coverage
    # (# of implemented items in a stub/ total number of items in a stub)
    return 100.0


def print_results(results: list[CoverageResult]) -> None:
    table = PrettyTable(
        field_names=["Abstraction", "Type", "Implementation", "Source Stub", "Coverage"],
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
                result.abstraction_node.name,
                result.abstraction_node.object_type,
                result.impl_file,
                result.stub_file,
                f"{result.coverage:.2f}%",
            ],
            divider=True,
        )

    print(table)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    stubs_path = project_root / "stubs/algopy-stubs"
    impl_path = project_root / "algopy_testing/src/algopy"
    results = compare_definitions(stubs_path, impl_path)
    print_results(results)


if __name__ == "__main__":
    main()
