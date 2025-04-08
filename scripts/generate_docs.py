#!/usr/bin/env python3

import ast
import functools
import subprocess
import symtable as st
import sys
import typing
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import attrs
from sphinx.cmd.build import main as sphinx_build

from puya import log

logger = log.get_logger(__name__)

VCS_ROOT = Path(__file__).parent.parent.resolve()

BASE_DIR = VCS_ROOT / "stubs"
MODULE_NAME = "algopy"
PACKAGE_ROOT = BASE_DIR / f"{MODULE_NAME}-stubs"

DOCS_DIR = VCS_ROOT / "docs"
STUBS_DOC_DIR = DOCS_DIR / f"{MODULE_NAME}-stubs"


def main() -> int:
    log.configure_stdio()
    generate_doc_stubs()
    return sphinx_build(
        [str(DOCS_DIR), str(DOCS_DIR / "_build"), "-W", "--keep-going", "-n", "-E"]
    )


def generate_doc_stubs() -> None:
    stub_files = _read_stub_files()

    @functools.cache
    def read_source(p: str) -> list[str]:
        (found,) = (sf for sf in stub_files.values() if str(sf.path) == p)
        return found.text.splitlines()

    for sf in stub_files.values():
        if sf.module_name == MODULE_NAME or (not sf.path.stem.startswith("_")):
            stub = DocStub.process_module(stub_files, read_source, sf.module_name)
            output_combined_stub(stub, STUBS_DOC_DIR / sf.path.name)


@attrs.frozen
class _PyFile:
    path: Path
    base_dir: Path
    module_name: str
    text: str
    module: ast.Module
    symtable: st.SymbolTable

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


@attrs.define(kw_only=True)
class ClassBases:
    klass: ast.ClassDef
    bases: list[ast.expr]
    protocol_bases: list[tuple[_PyFile, ast.ClassDef]]


@attrs.define
class SymbolCollector(ast.NodeVisitor):
    file: _PyFile
    read_source: Callable[[str], list[str] | None]
    all_classes: dict[str, tuple[_PyFile, ast.ClassDef]]
    inlined_protocols: dict[str, set[str]]
    symbols: dict[str, str] = attrs.field(factory=dict)
    last_stmt: ast.stmt | None = None
    _overloads: dict[str, list[ast.FunctionDef]] = attrs.field(factory=dict)

    def get_node_src(
        self,
        node: ast.AST,
        *,
        path: str | None = None,
        entire_lines: bool = True,
        include_decorators: bool = True,
    ) -> str:
        # TODO: add | ast.ClassDef
        if isinstance(node, ast.FunctionDef) and include_decorators:
            assert entire_lines
            if node.decorator_list:
                lineno = node.decorator_list[0].lineno
            else:
                lineno = node.lineno
        else:
            maybe_lineno = getattr(node, "lineno", None)
            assert isinstance(maybe_lineno, int)
            lineno = maybe_lineno
        return self.get_src(
            path=path,
            entire_lines=entire_lines,
            lineno=lineno,
            end_lineno=getattr(node, "end_lineno", None),
            col_offset=getattr(node, "col_offset", None),
            end_col_offset=getattr(node, "end_col_offset", None),
        )

    def get_src(
        self,
        *,
        lineno: int,
        end_lineno: int | None,
        col_offset: int | None,
        end_col_offset: int | None,
        path: str | None = None,
        entire_lines: bool = True,
    ) -> str:
        columns: tuple[int, int] | None = None
        if not entire_lines and end_col_offset is not None:
            assert col_offset is not None
            columns = (col_offset, end_col_offset)
        return self.get_src_from_lines(lineno, end_lineno or lineno, path, columns)

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
    def visit_Module(self, node: ast.Module) -> None:
        for stmt in node.body:
            self.visit(stmt)
            self.last_stmt = stmt
        for name, overload_list in self._overloads.items():
            self._visit_overload(name, overload_list)

    def _get_bases(self, klass: ast.ClassDef) -> ClassBases:
        bases = list[ast.expr]()
        inline = list[tuple[_PyFile, ast.ClassDef]]()
        for base in klass.bases:
            match base:
                case ast.Name(id=name) if name == "BytesBacked" or name.endswith("Protocol"):
                    inline.append(self.all_classes[name])
                case ast.Attribute(value=ast.Name(id="typing"), attr="Protocol"):
                    pass
                case _:
                    bases.append(base)
        return ClassBases(klass=klass, bases=bases, protocol_bases=inline)

    def _get_inlined_class(self, klass: ClassBases) -> str:
        # TODO: what about class keywords
        klass_str = f"class {klass.klass.name}"
        if klass.bases:
            klass_str += (
                f"({', '.join(self.get_node_src(b, entire_lines=False) for b in klass.bases)})"
            )
        src = [f"{klass_str}:"]
        src.extend(self.get_node_src(member) for member in klass.klass.body)
        for base_class_file, base_class in klass.protocol_bases:
            self.inlined_protocols.setdefault(base_class_file.module_name, set()).add(
                base_class.name
            )
            src.extend(
                self.get_node_src(member, path=str(base_class_file.path))
                for member in base_class.body
            )
        return "\n".join(src)

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        assert node.name not in self.all_classes
        self.all_classes[node.name] = self.file, node
        class_bases = self._get_bases(node)
        if class_bases.protocol_bases:
            self.symbols[node.name] = self._get_inlined_class(class_bases)
        else:
            self.symbols[node.name] = self.get_node_src(node)

    @typing.override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for dec in node.decorator_list:
            match dec:
                case ast.Attribute(value=ast.Name(id="typing"), attr="overload"):
                    self.symbols.setdefault(node.name, "")
                    self._overloads.setdefault(node.name, []).append(node)
                    return
        assert node.name not in self._overloads
        self.symbols[node.name] = self.get_node_src(node)

    def _visit_overload(self, name: str, overload_list: list[ast.FunctionDef]) -> None:
        line = min(o.decorator_list[0].lineno for o in overload_list)
        end_line = max(o.end_lineno for o in overload_list if o.end_lineno is not None)
        overloaded_src = self.get_src_from_lines(line, end_line)
        best_sig = _get_best_overload(overload_list)

        if not best_sig:
            src = overloaded_src
        else:
            best_sig_src = self.get_node_src(best_sig, include_decorators=False)
            src = f"{overloaded_src}\n{best_sig_src}"

        assert self.symbols[name] == ""
        self.symbols[name] = src

    @typing.override
    def visit_Assign(self, node: ast.Assign) -> None:
        lvalue = _get_lvalue(node)
        if not isinstance(lvalue, ast.Name):
            raise TypeError(f"Multi assignments are not supported: {lvalue}")
        # find actual rvalue src location by taking the entire statement and subtracting the lvalue
        self.symbols[lvalue.id] = self.get_src(
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            col_offset=lvalue.end_col_offset or node.col_offset,
            end_col_offset=node.end_col_offset,
        )

    @typing.override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        lvalue = node.target
        if not isinstance(lvalue, ast.Name):
            raise TypeError(f"Multi assignments are not supported: {lvalue}")
        # find actual rvalue src location by taking the entire statement and subtracting the lvalue
        self.symbols[lvalue.id] = self.get_src(
            lineno=node.lineno,
            end_lineno=node.end_lineno,
            col_offset=lvalue.end_col_offset or node.col_offset,
            end_col_offset=node.end_col_offset,
        )

    @typing.override
    def visit_Expr(self, node: ast.Expr) -> None:
        if (
            isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and isinstance(self.last_stmt, ast.Assign | ast.AnnAssign)
        ):
            lvalue = _get_lvalue(self.last_stmt)
            if isinstance(lvalue, ast.Name):
                self.symbols[lvalue.id] += "\n" + self.get_node_src(node.value)


def _get_best_overload(overloads: Sequence[ast.FunctionDef]) -> ast.FunctionDef | None:
    # this is good enough until a more complex case arises
    sorted_overloads = sorted(overloads, key=lambda f: _count_arguments(f.args), reverse=True)
    for func_def in sorted_overloads:
        docstring = ast.get_docstring(func_def)
        if docstring is not None:
            return func_def
    return sorted_overloads[0]


def _get_lvalue(node: ast.Assign | ast.AnnAssign) -> ast.expr:
    if isinstance(node, ast.AnnAssign):
        return node.target
    else:
        try:
            (lvalue,) = node.targets
        except ValueError as ex:
            raise ValueError(f"Multi assignments are not supported: {node}") from ex
        return lvalue


def _count_arguments(args: ast.arguments) -> int:
    positional = len(args.posonlyargs)
    regular = len(args.args)
    keyword = len(args.kwonlyargs)
    result = positional + regular + keyword
    if args.vararg is not None:
        result += 1
    if args.kwarg:
        result += 1
    return result


@attrs.define
class ModuleImports:
    from_imports: dict[str, str | None] = attrs.field(factory=dict)
    import_all: bool = False
    import_module: bool = False


@attrs.define
class ImportCollector(ast.NodeVisitor):
    collected_imports: dict[str, ModuleImports]

    def get_imports(self, module_id: str) -> ModuleImports:
        try:
            imports = self.collected_imports[module_id]
        except KeyError:
            imports = self.collected_imports[module_id] = ModuleImports()
        return imports

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        assert node.module is not None
        assert node.level in (0, None)
        imports = self.get_imports(node.module)
        for alias in node.names:
            if alias.name != "*":
                imports.from_imports[alias.name] = alias.asname

    @typing.override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname not in (None, alias.name):
                raise Exception("Aliasing symbols in stubs is not supported")

            imports = self.get_imports(alias.name)
            imports.import_module = True


@attrs.define
class DocStub(ast.NodeVisitor):
    read_source: Callable[[str], list[str] | None]
    file: _PyFile
    modules: Mapping[str, _PyFile]
    parsed_modules: dict[str, SymbolCollector] = attrs.field(factory=dict)
    all_classes: dict[str, tuple[_PyFile, ast.ClassDef]] = attrs.field(factory=dict)
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
        stub.visit(module.module)
        stub._add_all_symbols(module.module_name)  # noqa: SLF001
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
            collector.visit(file.module)
            self._collect_imports(file.module)
            return collector

    def _collect_imports(self, node: ast.AST) -> None:
        ImportCollector(self.collected_imports).visit(node)
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
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        assert node.module is not None
        assert node.level in (0, None)
        if not _should_inline_module(node.module):
            self._collect_imports(node)
        else:
            for alias in node.names:
                if alias.asname not in (None, alias.name):
                    raise Exception("Aliasing symbols in stubs is not supported")
                if alias.name == "*":
                    self._add_all_symbols(node.module)
                else:
                    module = self._get_module(node.module)
                    self.add_symbol(module, alias.name)

    def _add_all_symbols(self, module_id: str) -> None:
        module = self._get_module(module_id)
        for sym in module.symbols:
            self.add_symbol(module, sym)

    @typing.override
    def visit_Import(self, node: ast.Import) -> None:
        self._collect_imports(node)

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
    sys.exit(main())
