#!/usr/bin/env python3
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "puya" / "_vendor"))


import attrs
import mypy.build
import mypy.nodes
from mypy.visitor import NodeVisitor
from puya.compile import get_mypy_options
from puya.parse import parse_and_typecheck

SCRIPTS_DIR = Path(__file__).parent
VCS_ROOT = SCRIPTS_DIR.parent
SRC_DIR = VCS_ROOT / "src"
DOCS_DIR = VCS_ROOT / "docs"
STUBS_DIR = SRC_DIR / "puyapy-stubs"
STUBS_DOC_DIR = DOCS_DIR / "puyapy-stubs"


@attrs.define
class ModuleImports:
    from_imports: dict[str, str | None] = attrs.field(factory=dict)
    import_all: bool = False
    import_module: bool = False


def main() -> None:
    stubs = combine_stubs(STUBS_DIR / "__init__.pyi")
    output_combined_stub(stubs, STUBS_DOC_DIR / "__init__.pyi")
    run_sphinx()


def combine_stubs(path: Path) -> "StubVisitor":
    mypy_options = get_mypy_options()
    parse_result = parse_and_typecheck([path], mypy_options)
    read_source = parse_result.manager.errors.read_source
    assert read_source
    modules = parse_result.manager.modules
    puyapy_module: mypy.nodes.MypyFile = modules["puyapy"]
    stub_visitor = StubVisitor(read_source=read_source, file=puyapy_module, modules=modules)
    puyapy_module.accept(stub_visitor)
    return stub_visitor


def output_combined_stub(stubs: "StubVisitor", output: Path) -> None:
    # remove puyapy imports that have been inlined
    puyapy_direct_imports = stubs.collected_imports.get("puyapy", ModuleImports())
    other_puyapy_stubs = []
    for name in list(puyapy_direct_imports.from_imports):
        if name in stubs.collected_symbols or name in stubs.collected_assignments:
            del puyapy_direct_imports.from_imports[name]
        else:
            other_puyapy_stubs.append(name)

    lines = ["# ruff: noqa: A001, E501, F403, PYI021, PYI034"]
    rexported = list[str]()
    for module, imports in stubs.collected_imports.items():
        if imports.import_all:
            lines.append(f"import {module}")
        if imports.from_imports:
            rexported.extend(filter(None, imports.from_imports.values()))
            from_imports = ", ".join(_name_as(k, v) for k, v in imports.from_imports.items())
            lines.append(f"from {module} import {from_imports}")
    lines.extend(["", ""])

    # assemble __all__
    lines.append("__all__ = [")
    for symbol in (*rexported, *stubs.collected_assignments, *stubs.collected_symbols):
        if symbol.startswith("_"):
            continue
        lines.append(f'    "{symbol}",')
    lines.append("]")

    # assemble assignments
    for symbol in stubs.collected_assignments.values():
        lines.append(symbol)

    # assemble symbols
    for symbol in stubs.collected_symbols.values():
        lines.extend(["", "", symbol])

    # output and linting
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    for other_stub in other_puyapy_stubs:
        stub_file = f"{other_stub}.pyi"
        shutil.copy2(STUBS_DIR / stub_file, STUBS_DOC_DIR / stub_file)
    subprocess.run(["black", str(output)], check=True, cwd=VCS_ROOT)
    subprocess.run(["ruff", "--fix", str(output)], check=True, cwd=VCS_ROOT)


def run_sphinx() -> None:
    subprocess.run(
        ["sphinx-build", ".", "_build", "-W", "--keep-going", "-n", "-E"], check=True, cwd=DOCS_DIR
    )


@attrs.define
class SymbolCollector(NodeVisitor[None]):
    file: mypy.nodes.MypyFile
    symbols: dict[str, mypy.nodes.Node] = attrs.field(factory=dict)
    assignments: dict[str, mypy.nodes.Node] = attrs.field(factory=dict)

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            stmt.accept(self)

    def visit_class_def(self, o: mypy.nodes.ClassDef) -> None:
        self.symbols[o.name] = o

    def visit_func_def(self, o: mypy.nodes.FuncDef) -> None:
        self.symbols[o.name] = o

    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef) -> None:
        self.symbols[o.name] = o

    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt) -> None:
        try:
            (lvalue,) = o.lvalues
        except ValueError as ex:
            raise Exception(f"Multi assignments are not supported: {o}") from ex
        if not isinstance(lvalue, mypy.nodes.NameExpr):
            raise Exception(f"Multi assignments are not supported: {lvalue}")
        self.assignments[lvalue.name] = o.rvalue


@attrs.define
class ImportCollector(NodeVisitor[None]):
    collected_imports: dict[str, ModuleImports]

    def get_imports(self, module_id: str) -> ModuleImports:
        try:
            imports = self.collected_imports[module_id]
        except KeyError:
            imports = self.collected_imports[module_id] = ModuleImports()
        return imports

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            stmt.accept(self)

    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> None:
        imports = self.get_imports(o.id)
        for name, name_as in o.names:
            imports.from_imports[name] = name_as

    def visit_import(self, o: mypy.nodes.Import) -> None:
        for name, name_as in o.ids:
            if name != (name_as or name):
                raise Exception("Aliasing symbols in stubs is not supported")

            imports = self.get_imports(name)
            imports.import_all = True


@attrs.define
class StubVisitor(NodeVisitor[None]):
    read_source: Callable[[str], list[str] | None]
    file: mypy.nodes.MypyFile
    modules: dict[str, mypy.nodes.MypyFile]
    parsed_modules: dict[str, SymbolCollector] = attrs.field(factory=dict)
    collected_imports: dict[str, ModuleImports] = attrs.field(factory=dict)
    collected_assignments: dict[str, str] = attrs.field(factory=dict)
    collected_symbols: dict[str, str] = attrs.field(factory=dict)

    def _get_module(self, module_id: str) -> SymbolCollector:
        try:
            return self.parsed_modules[module_id]
        except KeyError:
            file = self.modules[module_id]
            self.parsed_modules[module_id] = collector = SymbolCollector(file=file)
            file.accept(collector)
            self._collect_imports(file)
            return collector

    def _collect_imports(self, o: mypy.nodes.Node) -> None:
        o.accept(ImportCollector(self.collected_imports))

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            stmt.accept(self)

    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> None:
        if not _should_inline_module(o.id):
            self._collect_imports(o)
            return
        module = self._get_module(o.id)
        for name, name_as in o.names:
            if name != (name_as or name):
                raise Exception("Aliasing symbols in stubs is not supported")

            self.add_symbol(module, name, is_symbol=name in module.symbols)

    def visit_import_all(self, o: mypy.nodes.ImportAll) -> None:
        if not _should_inline_module(o.id):
            self._collect_imports(o)
            return
        module = self._get_module(o.id)
        for sym in module.symbols:
            self.add_symbol(module, sym)
        for ass in module.assignments:
            self.add_symbol(module, ass, is_symbol=False)

    def visit_import(self, o: mypy.nodes.Import) -> None:
        self._collect_imports(o)

    def add_symbol(self, module: SymbolCollector, name: str, *, is_symbol: bool = True) -> None:
        src = self.read_source(module.file.path)
        if not src:
            raise Exception("Could not get src")
        node = module.symbols[name] if is_symbol else module.assignments[name]
        lines = "\n".join(src[node.line - 1 : node.end_line])
        existing = (
            self.collected_symbols.get(name) if is_symbol else self.collected_assignments.get(name)
        )
        if existing is not None and existing != lines:
            raise Exception(f"Duplicate definitions are not supported: {name}\n{lines}")
        if is_symbol:
            self.collected_symbols[name] = lines
        else:
            self.collected_assignments[name] = lines


def _name_as(name: str, name_as: str | None) -> str:
    if name_as is None:
        return name
    return f"{name} as {name_as}"


def _should_inline_module(module_id: str) -> bool:
    return module_id.startswith("puyapy._")


if __name__ == "__main__":
    main()
