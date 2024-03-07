#!/usr/bin/env python3
import subprocess
import sys
import typing
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "puya" / "_vendor"))


import attrs
import mypy.build
import mypy.nodes
from mypy.visitor import NodeVisitor
from puya.compile import get_mypy_options
from puya.parse import ParseResult, parse_and_typecheck

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
    parse_result = parse_and_typecheck([STUBS_DIR], get_mypy_options())
    output_doc_stubs(parse_result)
    run_sphinx()


def output_doc_stubs(parse_result: ParseResult) -> None:
    # parse and output reformatted __init__.pyi
    stub = DocStub.process_module(parse_result, "puyapy")
    puyapy_direct_imports = stub.collected_imports["puyapy"]
    # remove any puyapy imports that are now defined in __init__.py itself
    output_combined_stub(stub, STUBS_DOC_DIR / "__init__.pyi")

    # remaining imports from puyapy are other public modules
    # parse and output them too
    for other_stub_name in puyapy_direct_imports.from_imports:
        stub = DocStub.process_module(parse_result, f"puyapy.{other_stub_name}")
        output_combined_stub(stub, STUBS_DOC_DIR / f"{other_stub_name}.pyi")


def output_combined_stub(stubs: "DocStub", output: Path) -> None:
    # remove puyapy imports that have been inlined
    lines = ["# ruff: noqa: A001, E501, F403, PYI021, PYI034"]
    rexported = list[str]()
    for module, imports in stubs.collected_imports.items():
        if imports.import_module:
            lines.append(f"import {module}")
        if imports.from_imports:
            rexported.extend(filter(None, imports.from_imports.values()))
            from_imports = ", ".join(_name_as(k, v) for k, v in imports.from_imports.items())
            lines.append(f"from {module} import {from_imports}")
    lines.extend(["", ""])

    # assemble __all__
    lines.append("__all__ = [")
    for symbol in (*rexported, *stubs.collected_symbols):
        if symbol.startswith("_"):
            continue
        lines.append(f'    "{symbol}",')
    lines.append("]")

    # assemble symbols
    for symbol in stubs.collected_symbols.values():
        lines.append(symbol)

    # output and linting
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))

    subprocess.run(["black", str(output)], check=True, cwd=VCS_ROOT)
    subprocess.run(["ruff", "--fix", str(output)], check=True, cwd=VCS_ROOT)


def run_sphinx() -> None:
    subprocess.run(
        ["sphinx-build", ".", "_build", "-W", "--keep-going", "-n", "-E"], check=True, cwd=DOCS_DIR
    )


@attrs.define(kw_only=True)
class ClassBases:
    klass: mypy.nodes.ClassDef
    bases: list[mypy.nodes.Expression]
    protocol_bases: list[tuple[mypy.nodes.MypyFile, mypy.nodes.ClassDef]]


@attrs.define
class SymbolCollector(NodeVisitor[None]):
    file: mypy.nodes.MypyFile
    read_source: Callable[[str], list[str] | None]
    all_classes: dict[str, tuple[mypy.nodes.MypyFile, mypy.nodes.ClassDef]]
    inlined_protocols: dict[str, set[str]]
    symbols: dict[str, str] = attrs.field(factory=dict)

    def get_src(
        self, node: mypy.nodes.Context, *, path: str | None = None, entire_lines: bool = True
    ) -> str:
        columns: tuple[int, int] | None = None
        if node.end_column and not entire_lines:
            columns = (node.column, node.end_column)
        return self.get_src_from_lines(node.line, node.end_line or node.line, path, columns)

    def get_src_from_lines(
        self,
        line: int,
        end_line: int,
        path: str | None = None,
        columns: tuple[int, int] | None = None,
    ) -> str:
        src = self.read_source(path or self.file.path)
        if not src:
            raise Exception("Could not get src")
        lines = src[line - 1 : end_line]
        if columns:
            lines[-1] = lines[-1][: columns[1]]
            lines[0] = lines[0][columns[0] :]
        return "\n".join(lines)

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            stmt.accept(self)

    def _get_bases(self, klass: mypy.nodes.ClassDef) -> ClassBases:
        bases = list[mypy.nodes.Expression]()
        inline = list[tuple[mypy.nodes.MypyFile, mypy.nodes.ClassDef]]()
        for base in klass.base_type_exprs:
            if (
                isinstance(base, mypy.nodes.NameExpr)
                and _should_inline_module(base.fullname)
                and self._is_protocol(base.fullname)
            ):
                inline.append(self.all_classes[base.fullname])
            else:
                bases.append(base)
        return ClassBases(klass=klass, bases=bases, protocol_bases=inline)

    def _get_inlined_class(self, klass: ClassBases) -> str:
        # TODO: what about class keywords
        klass_str = f"class {klass.klass.name}"
        if klass.bases:
            klass_str += f"({', '.join(self.get_src(b, entire_lines=False) for b in klass.bases)})"
        src = [f"{klass_str}:"]
        for member in klass.klass.defs.body:
            src.append(self.get_src(member))
        for base_class_file, base_class in klass.protocol_bases:
            self.inlined_protocols.setdefault(base_class_file.fullname, set()).add(base_class.name)
            for member in base_class.defs.body:
                src.append(self.get_src(member, path=base_class_file.path))
        return "\n".join(src)

    def visit_class_def(self, o: mypy.nodes.ClassDef) -> None:
        self.all_classes[o.fullname] = self.file, o
        class_bases = self._get_bases(o)
        if class_bases.protocol_bases:
            self.symbols[o.name] = self._get_inlined_class(class_bases)
        else:
            self.symbols[o.name] = self.get_src(o)

    def visit_func_def(self, o: mypy.nodes.FuncDef) -> None:
        self.symbols[o.name] = self.get_src(o)

    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef) -> None:
        line = o.line
        end_line = o.end_line or o.line
        for item in o.items:
            end_line = max(end_line, item.end_line or item.line)
        overloaded_src = self.get_src_from_lines(line, end_line)
        best_sig = _get_documented_overload(o)

        if not best_sig:
            src = overloaded_src
        else:
            best_sig_src = self.get_src(best_sig)
            src = f"{overloaded_src}\n{best_sig_src}"

        self.symbols[o.name] = src

    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt) -> None:
        try:
            (lvalue,) = o.lvalues
        except ValueError as ex:
            raise Exception(f"Multi assignments are not supported: {o}") from ex
        if not isinstance(lvalue, mypy.nodes.NameExpr):
            raise Exception(f"Multi assignments are not supported: {lvalue}")
        # find actual rvalue src location by taking the entire statement and subtracting the lvalue
        loc = mypy.nodes.Context()
        loc.set_line(o)
        if lvalue.end_column:
            loc.column = lvalue.end_column
        self.symbols[lvalue.name] = self.get_src(loc)

    def _is_protocol(self, fullname: str) -> bool:
        try:
            klass = self.all_classes[fullname]
        except KeyError:
            return False
        info: mypy.nodes.TypeInfo = klass[1].info
        return info.is_protocol


def _get_documented_overload(o: mypy.nodes.OverloadedFuncDef) -> mypy.nodes.FuncDef | None:
    best_overload: mypy.nodes.FuncDef | None = None
    for overload in o.items:
        match overload:
            case mypy.nodes.Decorator(func=func_def):
                pass
            case mypy.nodes.FuncDef() as func_def:
                pass
            case _:
                raise Exception("Only function overloads supported")

        docstring = _get_docstring(func_def)

        # this is good enough until a more complex case arises
        if docstring and (
            not best_overload or len(func_def.arguments) > len(best_overload.arguments)
        ):
            best_overload = func_def
    return best_overload


def _get_docstring(func_def: mypy.nodes.FuncDef) -> str | None:
    match func_def:
        case mypy.nodes.FuncDef(docstring=str() as docstring):
            return docstring
        case mypy.nodes.FuncDef(
            body=mypy.nodes.Block(
                body=[
                    mypy.nodes.ExpressionStmt(
                        expr=mypy.nodes.StrExpr(value=docstring),
                    )
                ]
            )
        ):
            return docstring
        case _:
            return None


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
            imports.import_module = True


@attrs.define
class DocStub(NodeVisitor[None]):
    read_source: Callable[[str], list[str] | None]
    file: mypy.nodes.MypyFile
    modules: dict[str, mypy.nodes.MypyFile]
    parsed_modules: dict[str, SymbolCollector] = attrs.field(factory=dict)
    all_classes: dict[str, tuple[mypy.nodes.MypyFile, mypy.nodes.ClassDef]] = attrs.field(
        factory=dict
    )
    collected_imports: dict[str, ModuleImports] = attrs.field(factory=dict)
    inlined_protocols: dict[str, set[str]] = attrs.field(factory=dict)
    collected_symbols: dict[str, str] = attrs.field(factory=dict)

    @classmethod
    def process_module(cls, parse_result: ParseResult, module_id: str) -> typing.Self:
        read_source = parse_result.manager.errors.read_source
        assert read_source
        modules = parse_result.manager.modules
        module: mypy.nodes.MypyFile = modules[module_id]
        stub = cls(read_source=read_source, file=module, modules=modules)
        module.accept(stub)
        stub._remove_inlined_symbols()  # noqa: SLF001
        return stub

    def _get_module(self, module_id: str) -> SymbolCollector:
        try:
            return self.parsed_modules[module_id]
        except KeyError:
            file = self.modules[module_id]
            self.parsed_modules[module_id] = collector = SymbolCollector(
                file=file,
                read_source=self.read_source,
                all_classes=self.all_classes,
                inlined_protocols=self.inlined_protocols,
            )
            file.accept(collector)
            self._collect_imports(file)
            return collector

    def _collect_imports(self, o: mypy.nodes.Node) -> None:
        o.accept(ImportCollector(self.collected_imports))
        self._remove_inlined_symbols()

    def _remove_inlined_symbols(self) -> None:
        for module, imports in self.collected_imports.items():
            inlined_protocols = self.inlined_protocols.get(module, ())
            if imports.import_module and module in self.collected_symbols:
                raise Exception(f"Symbol/import collision: {module}")
            for name, name_as in list(imports.from_imports.items()):
                if name in inlined_protocols:
                    print(f"Removed inlined protocol: {name}")
                    del imports.from_imports[name]
                    del self.collected_symbols[name]
                elif name in self.collected_symbols:
                    if name_as is None:
                        del imports.from_imports[name]
                    else:
                        print(f"Symbol/import collision: from {module} import {name} as {name_as}")

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            stmt.accept(self)
        self._add_all_symbols(o.fullname)

    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> None:
        if not _should_inline_module(o.id):
            self._collect_imports(o)
            return
        module = self._get_module(o.id)
        name_mapping = dict(o.names)
        for name in module.symbols:
            try:
                name_as = name_mapping[name]
            except KeyError:
                continue
            if name != (name_as or name):
                raise Exception("Aliasing symbols in stubs is not supported")
            self.add_symbol(module, name)

    def visit_import_all(self, o: mypy.nodes.ImportAll) -> None:
        if _should_inline_module(o.id):
            self._add_all_symbols(o.id)
        else:
            self._collect_imports(o)

    def _add_all_symbols(self, module_id: str) -> None:
        module = self._get_module(module_id)
        for sym in module.symbols:
            self.add_symbol(module, sym)

    def visit_import(self, o: mypy.nodes.Import) -> None:
        self._collect_imports(o)

    def add_symbol(self, module: SymbolCollector, name: str) -> None:
        lines = module.symbols[name]
        existing = self.collected_symbols.get(name)
        if existing is not None and existing != lines:
            raise Exception(f"Duplicate definitions are not supported: {name}\n{lines}")
        self.collected_symbols[name] = lines


def _name_as(name: str, name_as: str | None) -> str:
    if name_as is None:
        return name
    return f"{name} as {name_as}"


def _should_inline_module(module_id: str) -> bool:
    return module_id.startswith("puyapy._")


if __name__ == "__main__":
    main()
