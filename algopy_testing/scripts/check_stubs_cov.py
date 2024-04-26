import ast
import os
from pathlib import Path

from prettytable import PrettyTable


def list_python_files(directory: Path) -> list[str]:
    return [
        f
        for f in os.listdir(directory)
        if f.endswith(".py") or f.endswith(".pyi") and not f.startswith("_")
    ]


def parse_python_file(filepath: Path) -> ast.Module:
    with filepath.open() as file:
        tree = ast.parse(file.read(), filename=filepath)
    return tree


def extract_definitions(tree: ast.Module) -> list[str]:
    return list(
        {node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.ClassDef)}
    )


def compare_definitions(stubs_dir: Path, impl_dir: Path):
    stubs_files = list_python_files(stubs_dir)
    impl_files = list_python_files(impl_dir)

    table = PrettyTable(
        field_names=["File", "Status", "Missing Definitions", "Coverage"],
        sortby="Coverage",
        header=True,
        border=True,
        padding_width=2,
        left_padding_width=0,
        right_padding_width=1,
        align="l",
        max_width=100,
    )

    for stub_file in stubs_files:
        stub_tree = parse_python_file(stubs_dir / stub_file)
        stub_defs = extract_definitions(stub_tree)

        impl_file_name = stub_file.replace(".pyi", ".py")
        if impl_file_name in impl_files:
            impl_tree = parse_python_file(impl_dir / impl_file_name)
            impl_defs = extract_definitions(impl_tree)

            missing_in_impl = set(stub_defs) - set(impl_defs)
            # Calculate coverage
            coverage = (
                ((len(stub_defs) - len(missing_in_impl)) / len(stub_defs)) * 100
                if stub_defs
                else 0
            )
            coverage_str = f"{coverage:.2f}%"

            if missing_in_impl:
                table.add_row(
                    [
                        impl_file_name,
                        "Missing definitions",
                        ", ".join(missing_in_impl),
                        coverage_str,
                    ],
                    divider=True,
                )
            else:
                # If there are no missing definitions, coverage is 100%
                table.add_row([impl_file_name, "Full coverage", "None", "100.00%"], divider=True)
        else:
            table.add_row([stub_file, "Implementation not found", "N/A", "0.00%"], divider=True)

    # Print the table
    print(table)  # noqa: T201


def main():
    project_root = Path(__file__).resolve().parents[2]
    stubs_path = project_root / "stubs/algopy-stubs"
    impl_path = project_root / "algopy_testing/src/algopy"
    compare_definitions(stubs_path, impl_path)


if __name__ == "__main__":
    main()
