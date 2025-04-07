#!/usr/bin/env python3

import ast
import functools
import subprocess
import symtable as st
import sys
import typing
from collections.abc import Callable, Mapping
from pathlib import Path

import attrs
import mypy.build
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options

from puya import log

logger = log.get_logger(__name__)

VCS_ROOT = Path(__file__).parent.parent.resolve()

BASE_DIR = VCS_ROOT / "stubs"
MODULE_NAME = "algopy"
PACKAGE_ROOT = BASE_DIR / f"{MODULE_NAME}-stubs"

STUBS_DOC_DIR = VCS_ROOT / "docs" / f"{MODULE_NAME}-stubs"


def main() -> None:
    log.configure_stdio()
    generate_doc_stubs()
    subprocess.run(
        ["sphinx-build", ".", "_build", "-W", "--keep-going", "-n", "-E"], check=True, cwd=DOCS_DIR
    )


def generate_doc_stubs() -> None:
    stub_files = _read_stub_files()

    stub_files = parse_and_typecheck(stub_files)

    @functools.cache
    def read_source(p: str) -> list[str]:
        (found,) = (sf for sf in stub_files.values() if str(sf.path) == p)
        return found.text.splitlines()

    for sf in stub_files.values():
        if sf.module_name == MODULE_NAME or (not sf.path.stem.startswith("_")):
            stub = DocStub.process_module(stub_files, read_source, sf.module_name)
            output_combined_stub(stub, STUBS_DOC_DIR / sf.path.name)


def parse_and_typecheck(stub_files: "Mapping[str, _PyFile]") -> "Mapping[str, _PyFile]":
    """Generate the ASTs from the build sources, and all imported modules (recursively)"""

    mypy_options = mypy.options.Options()
    mypy_options.preserve_asts = True
    mypy_options.include_docstrings = True

    result = mypy.build.build(
        sources=[
            mypy.modulefinder.BuildSource(
                path=str(sf.path),
                module=sf.module_name,
                text=sf.text,
                base_dir=str(sf.base_dir),
            )
            for sf in stub_files.values()
        ],
        options=mypy_options,
    )
    if result.errors:
        for msg in result.errors:
            print(msg, file=sys.stderr)
        raise RuntimeError("parsing failed")

    return {
        k: attrs.evolve(v, mypy_file=result.manager.modules[v.module_name])
        for k, v in stub_files.items()
    }


@attrs.frozen
class _PyFile:
    path: Path
    base_dir: Path
    module_name: str
    text: str
    module: ast.Module
    symtable: st.SymbolTable
    _mypy_file: mypy.nodes.MypyFile | None = None

    @property
    def mypy_file(self) -> mypy.nodes.MypyFile:
        assert self._mypy_file is not None
        return self._mypy_file

    @classmethod
    def from_path(cls, p: Path) -> typing.Self:
        p = p.resolve()
        assert p.parent == PACKAGE_ROOT
        if p.stem == "__init__":
            module_name = MODULE_NAME
        else:
            module_name = ".".join((MODULE_NAME, p.stem))

        text = p.read_text("utf8")
        module = ast.parse(text, filename=p.name, mode="exec", type_comments=True)
        symtable = st.symtable(text, filename=p.name, compile_type="exec")
        return cls(
            path=p,
            base_dir=BASE_DIR,
            module_name=module_name,
            text=text,
            module=module,
            symtable=symtable,
        )


def _read_stub_files() -> Mapping[str, _PyFile]:
    result = {}
    for p in PACKAGE_ROOT.iterdir():
        if p.is_dir():
            if not p.name.startswith("."):
                raise RuntimeError("directories not handled")
        elif p.is_file() and p.suffix == ".pyi":
            pf = _PyFile.from_path(p)
            assert pf.module_name not in result
            result[pf.module_name] = pf
    return result


def output_combined_stub(stubs: "DocStub", output: Path) -> None:
    # remove algopy imports that have been inlined
    lines = ["# ruff: noqa: A001, E501, F403, PYI021, PYI034, W291"]
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
    lines.extend(stubs.collected_symbols.values())

    # output and linting
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))

    subprocess.run(["ruff", "format", str(output)], check=True, cwd=VCS_ROOT)
    subprocess.run(["ruff", "check", "--fix", str(output)], check=True, cwd=VCS_ROOT)


class MyNodeVisitor:
    def visit(self, o: mypy.nodes.Node) -> None:
        match o:
            case mypy.nodes.MypyFile():
                self.visit_mypy_file(o)
            case mypy.nodes.ImportFrom():
                self.visit_import_from(o)
            case mypy.nodes.Import():
                self.visit_import(o)
            case mypy.nodes.ImportAll():
                self.visit_import_all(o)
            case mypy.nodes.ClassDef():
                self.visit_class_def(o)
            case mypy.nodes.FuncDef():
                self.visit_func_def(o)
            case mypy.nodes.OverloadedFuncDef():
                self.visit_overloaded_func_def(o)
            case mypy.nodes.AssignmentStmt():
                self.visit_assignment_stmt(o)
            case mypy.nodes.ExpressionStmt():
                self.visit_expression_stmt(o)
            case _:
                raise RuntimeError(f"unsupported node type: {type(o).__name__}")

    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        pass

    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> None:
        pass

    def visit_import(self, o: mypy.nodes.Import) -> None:
        pass

    def visit_import_all(self, o: mypy.nodes.ImportAll) -> None:
        pass

    def visit_class_def(self, o: mypy.nodes.ClassDef) -> None:
        pass

    def visit_func_def(self, o: mypy.nodes.FuncDef) -> None:
        pass

    def visit_overloaded_func_def(self, o: mypy.nodes.OverloadedFuncDef) -> None:
        pass

    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt) -> None:
        pass

    def visit_expression_stmt(self, o: mypy.nodes.ExpressionStmt) -> None:
        pass


@attrs.define(kw_only=True)
class ClassBases:
    klass: mypy.nodes.ClassDef
    bases: list[mypy.nodes.Expression]
    protocol_bases: list[tuple[_PyFile, mypy.nodes.ClassDef]]


@attrs.define
class SymbolCollector(MyNodeVisitor):
    file: _PyFile
    read_source: Callable[[str], list[str] | None]
    all_classes: dict[str, tuple[_PyFile, mypy.nodes.ClassDef]]
    inlined_protocols: dict[str, set[str]]
    symbols: dict[str, str] = attrs.field(factory=dict)
    last_stmt: mypy.nodes.Statement | None = None

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
        src = self.read_source(path or str(self.file.path))
        if not src:
            raise Exception("Could not get src")
        lines = src[line - 1 : end_line]
        if columns:
            lines[-1] = lines[-1][: columns[1]]
            lines[0] = lines[0][columns[0] :]
        return "\n".join(lines)

    @typing.override
    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            self.visit(stmt)
            self.last_stmt = stmt

    def _get_bases(self, klass: mypy.nodes.ClassDef) -> ClassBases:
        bases = list[mypy.nodes.Expression]()
        inline = list[tuple[_PyFile, mypy.nodes.ClassDef]]()
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
        src.extend(self.get_src(member) for member in klass.klass.defs.body)
        for base_class_file, base_class in klass.protocol_bases:
            self.inlined_protocols.setdefault(base_class_file.module_name, set()).add(
                base_class.name
            )
            src.extend(
                self.get_src(member, path=str(base_class_file.path))
                for member in base_class.defs.body
            )
        return "\n".join(src)

    @typing.override
    def visit_class_def(self, o: mypy.nodes.ClassDef) -> None:
        self.all_classes[o.fullname] = self.file, o
        class_bases = self._get_bases(o)
        if class_bases.protocol_bases:
            self.symbols[o.name] = self._get_inlined_class(class_bases)
        else:
            self.symbols[o.name] = self.get_src(o)

    @typing.override
    def visit_func_def(self, o: mypy.nodes.FuncDef) -> None:
        self.symbols[o.name] = self.get_src(o)

    @typing.override
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

    @typing.override
    def visit_assignment_stmt(self, o: mypy.nodes.AssignmentStmt) -> None:
        try:
            (lvalue,) = o.lvalues
        except ValueError as ex:
            raise ValueError(f"Multi assignments are not supported: {o}") from ex
        if not isinstance(lvalue, mypy.nodes.NameExpr):
            raise TypeError(f"Multi assignments are not supported: {lvalue}")
        # find actual rvalue src location by taking the entire statement and subtracting the lvalue
        loc = mypy.nodes.Context()
        loc.set_line(o)
        if lvalue.end_column:
            loc.column = lvalue.end_column
        self.symbols[lvalue.name] = self.get_src(loc)

    @typing.override
    def visit_expression_stmt(self, o: mypy.nodes.ExpressionStmt) -> None:
        if isinstance(o.expr, mypy.nodes.StrExpr) and isinstance(
            self.last_stmt, mypy.nodes.AssignmentStmt
        ):
            (lvalue,) = self.last_stmt.lvalues
            if isinstance(lvalue, mypy.nodes.NameExpr):
                self.symbols[lvalue.name] += "\n" + self.get_src(o.expr)

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

        docstring = func_def.docstring

        # this is good enough until a more complex case arises
        if docstring and (
            not best_overload or len(func_def.arguments) > len(best_overload.arguments)
        ):
            best_overload = func_def
    return best_overload


@attrs.define
class ModuleImports:
    from_imports: dict[str, str | None] = attrs.field(factory=dict)
    import_all: bool = False
    import_module: bool = False


@attrs.define
class ImportCollector(MyNodeVisitor):
    collected_imports: dict[str, ModuleImports]

    def get_imports(self, module_id: str) -> ModuleImports:
        try:
            imports = self.collected_imports[module_id]
        except KeyError:
            imports = self.collected_imports[module_id] = ModuleImports()
        return imports

    @typing.override
    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            self.visit(stmt)

    @typing.override
    def visit_import_from(self, o: mypy.nodes.ImportFrom) -> None:
        imports = self.get_imports(o.id)
        for name, name_as in o.names:
            imports.from_imports[name] = name_as

    @typing.override
    def visit_import(self, o: mypy.nodes.Import) -> None:
        for name, name_as in o.ids:
            if name != (name_as or name):
                raise Exception("Aliasing symbols in stubs is not supported")

            imports = self.get_imports(name)
            imports.import_module = True


@attrs.define
class DocStub(MyNodeVisitor):
    read_source: Callable[[str], list[str] | None]
    file: _PyFile
    modules: Mapping[str, _PyFile]
    parsed_modules: dict[str, SymbolCollector] = attrs.field(factory=dict)
    all_classes: dict[str, tuple[_PyFile, mypy.nodes.ClassDef]] = attrs.field(factory=dict)
    collected_imports: dict[str, ModuleImports] = attrs.field(factory=dict)
    inlined_protocols: dict[str, set[str]] = attrs.field(factory=dict)
    collected_symbols: dict[str, str] = attrs.field(factory=dict)

    @classmethod
    def process_module(
        cls,
        modules: Mapping[str, _PyFile],
        read_source: Callable[[str], list[str] | None],
        module_id: str,
    ) -> typing.Self:
        module = modules[module_id]
        stub = cls(read_source=read_source, file=module, modules=modules)
        stub.visit(module.mypy_file)
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
            collector.visit(file.mypy_file)
            self._collect_imports(file.mypy_file)
            return collector

    def _collect_imports(self, o: mypy.nodes.Node) -> None:
        ImportCollector(self.collected_imports).visit(o)
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

    @typing.override
    def visit_mypy_file(self, o: mypy.nodes.MypyFile) -> None:
        for stmt in o.defs:
            self.visit(stmt)
        self._add_all_symbols(o.fullname)

    @typing.override
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

    @typing.override
    def visit_import_all(self, o: mypy.nodes.ImportAll) -> None:
        if _should_inline_module(o.id):
            self._add_all_symbols(o.id)
        else:
            self._collect_imports(o)

    def _add_all_symbols(self, module_id: str) -> None:
        module = self._get_module(module_id)
        for sym in module.symbols:
            self.add_symbol(module, sym)

    @typing.override
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
    return module_id.startswith(f"{MODULE_NAME}._")


if __name__ == "__main__":
    main()
