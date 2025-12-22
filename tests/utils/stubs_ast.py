import ast
import builtins
import functools
import typing
from collections.abc import Mapping
from enum import Enum
from pathlib import Path

import attrs

from tests import STUBS_DIR
from tests.utils import get_module_name_from_path


@attrs.define
class TypeNode:
    is_array: bool = attrs.field(default=False)
    types: "list[str | TypeNode]" = attrs.field(factory=list)


class ArgKind(Enum):
    # Positional argument
    ARG_POS = 0
    # Positional, optional argument (functions only, not calls)
    ARG_OPT = 1
    # Keyword argument x=y in call, or keyword-only function arg
    ARG_NAMED = 3
    # In an argument list, keyword-only and also optional
    ARG_NAMED_OPT = 5


@attrs.define
class ArgNode:
    name: str
    kind: ArgKind = attrs.field(default=ArgKind.ARG_POS)
    type: TypeNode = attrs.field(factory=TypeNode)


@attrs.define
class FunctionNode:
    name: str
    args: list[ArgNode] = attrs.field(factory=list)
    return_type: TypeNode = attrs.field(factory=TypeNode)


@attrs.define
class PropertyNode:
    name: str
    type: TypeNode = attrs.field(factory=TypeNode)


@attrs.define
class ClassNode:
    name: str
    properties: dict[str, PropertyNode] = attrs.field(factory=dict)
    functions: dict[str, FunctionNode] = attrs.field(factory=dict)
    bases: list[str] = attrs.field(factory=list)


@attrs.define
class ModuleAST:
    path: Path
    tree: ast.AST
    module_name: str


@attrs.define
class ResolvedSymbol:
    module: str
    name: str
    source: str

    @property
    def friendly_name(self) -> str:
        return f"{self.module}.{self.name}"

    @property
    def full_name(self) -> str:
        return f"{self.source}.{self.name}"


class ClassCollector(ast.NodeVisitor):
    """Collect top-level classes and build ClassNode instances."""

    def __init__(self, module_name: str, module_symbols: list[ResolvedSymbol]) -> None:
        self.module_name = module_name
        self.module_symbols = module_symbols
        self.classes = list[ClassNode]()

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_node = ClassNode(name=f"{self.module_name}.{node.name}")

        # Extend the class_node with collected bases
        base_class_collector = _BaseClassCollector(self.module_name, self.module_symbols)
        base_class_collector.visit(node)
        class_node.bases.extend(base_class_collector.result)

        # Extend the class_node with collected members
        class_attribute_collector = _ClassAttributeCollector(self.module_symbols)
        class_attribute_collector.visit(node)
        class_node.properties.update({p.name: p for p in class_attribute_collector.properties})
        class_node.functions.update({f.name: f for f in class_attribute_collector.functions})

        self.classes.append(class_node)


class _BaseClassCollector(ast.NodeVisitor):
    def __init__(self, module_name: str, module_symbols: list[ResolvedSymbol]) -> None:
        self.bases = list[str]()
        self.current_module_name = module_name
        self.module_symbols = module_symbols

    @property
    def result(self) -> list[str]:
        def _get_full_name(name: str) -> str:
            module_name = _get_module_name_from_imports(name, self.module_symbols)
            return f"{module_name or self.current_module_name}.{name}"

        return [_get_full_name(name) for name in self.bases]

    @typing.override
    def visit_Attribute(self, node: ast.Attribute) -> None:
        # skip typing.* bases
        if isinstance(node.value, ast.Name) and node.value.id != "typing":
            self.bases.append(f"{node.value.id}.{node.attr}")

    @typing.override
    def visit_Name(self, node: ast.Name) -> None:
        self.bases.append(node.id)

    @typing.override
    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self.bases.append(node.value)

    @typing.override
    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.visit(node.value)

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for b in node.bases:
            self.visit(b)


class _ClassAttributeCollector(ast.NodeVisitor):
    """Visitor to collect properties and functions from a class body.

    We explicitly implement visit_ methods for the node types we care about
    and avoid generic traversal so nested definitions are not processed.
    """

    def __init__(self, module_symbols: list[ResolvedSymbol]) -> None:
        self.properties = list[PropertyNode]()
        self.functions = list[FunctionNode]()
        self.module_symbols = module_symbols

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for stmt in node.body:
            self.visit(stmt)

    @typing.override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # Only collect simple name targets (e.g., "x: int")
        if isinstance(node.target, ast.Name):
            self.properties.append(
                PropertyNode(
                    name=node.target.id,
                    type=self._get_type_node(node.annotation),
                )
            )

    @typing.override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Skip property deleters entirely
        if self._is_deleter(node.decorator_list):
            return

        # Property-like methods (@property or setter)
        if self._is_property_method(node.decorator_list):
            self.properties.append(
                PropertyNode(
                    name=node.name,
                    type=self._get_type_node(node.returns),
                )
            )
            return

        # Regular function/method
        args = node.args
        pos_args_len = len(args.posonlyargs) + len(args.args)
        pos_defaults_start_index = pos_args_len - len(args.defaults)
        arg_kinds = [
            ArgKind.ARG_OPT if i >= pos_defaults_start_index else ArgKind.ARG_POS
            for i in range(pos_args_len)
        ] + [
            ArgKind.ARG_NAMED_OPT if args.kw_defaults[i] is not None else ArgKind.ARG_NAMED
            for i, _ in enumerate(args.kwonlyargs)
        ]

        arg_nodes = [
            ArgNode(
                name=a.arg,
                type=self._get_type_node(a.annotation),
                kind=arg_kinds[idx],
            )
            for idx, a in enumerate(args.posonlyargs + args.args + args.kwonlyargs)
        ]
        self.functions.append(
            FunctionNode(
                name=node.name,
                args=arg_nodes,
                return_type=self._get_type_node(node.returns),
            )
        )

    def _is_property_method(self, decorators: list[ast.expr]) -> bool:
        """Check if a method has property-related decorators."""
        return any(
            (isinstance(d, ast.Name) and d.id == "property")
            or (isinstance(d, ast.Attribute) and d.attr == "setter")
            for d in decorators
        )

    def _is_deleter(self, decorators: list[ast.expr]) -> bool:
        """Check if a method is a property deleter."""
        return any(isinstance(d, ast.Attribute) and d.attr == "deleter" for d in decorators)

    def _get_type_node(self, type_expr: ast.expr | None) -> TypeNode:
        if type_expr is None:
            return TypeNode()
        type_expr_visitor = _TypeExprVisitor(self.module_symbols)
        type_expr_visitor.visit(type_expr)
        return type_expr_visitor.result or TypeNode()


class _TypeExprVisitor(ast.NodeVisitor):
    def __init__(self, module_symbols: list[ResolvedSymbol]) -> None:
        self.module_symbols = module_symbols
        self.types = list[str | TypeNode]()
        self.is_array = False

    @property
    def result(self) -> TypeNode | None:
        if len(self.types) == 0:
            return None
        return TypeNode(types=list(self.types), is_array=self.is_array)

    @typing.override
    def visit_Name(self, node: ast.Name) -> None:
        module = _get_module_name_from_imports(node.id, self.module_symbols)
        self.types = [f"{module}.{node.id}" if module else node.id]

    @typing.override
    def visit_Attribute(self, node: ast.Attribute) -> None:
        # typing.Self
        if isinstance(node.value, ast.Name) and node.value.id == "typing" and node.attr == "Self":
            self.types = ["typing.Self"]
            return

        # other attribute forms like X.Y -> "X.Y"
        if isinstance(node.value, ast.Name):
            self.types = [f"{node.value.id}.{node.attr}"]

    @typing.override
    def visit_BinOp(self, node: ast.BinOp) -> None:
        # handle union types (PEP 604): A | B
        if isinstance(node.op, ast.BitOr):
            left = self._visit_expr(node.left, self.module_symbols)
            right = self._visit_expr(node.right, self.module_symbols)
            types = list[str | TypeNode]()
            if left:
                types.append(left)
            if right:
                types.append(right)
            self.types = types or []
            self.is_array = (left.is_array if left else False) and (
                right.is_array if right else False
            )

    @typing.override
    def visit_Subscript(self, node: ast.Subscript) -> None:
        # Iterator[...] or Iterable[...] => array/variadic
        if isinstance(node.value, ast.Name) and node.value.id in ("Iterator", "Iterable"):
            self.is_array = True
            sl = node.slice

            # simple name like Iterator[T]
            if isinstance(sl, ast.Name):
                module = _get_module_name_from_imports(sl.id, self.module_symbols)
                self.types = [f"{module}.{sl.id}" if module else sl.id]
                return

            # more complex slice -> recurse
            t = self._visit_expr(sl, self.module_symbols)
            self.types = [t] if t else []
            return

        # Subscript with tuple of elements -> treat as array of multiple types
        if isinstance(node.slice, ast.Tuple):
            self.is_array = True
            elts = node.slice.elts
            types = list[str | TypeNode]()
            for elt in elts:
                t = self._visit_expr(elt, self.module_symbols)
                if t:
                    types.append(t)
            self.types = types or []

    def _visit_expr(self, expr: ast.expr, module_symbols: list[ResolvedSymbol]) -> TypeNode | None:
        visitor = _TypeExprVisitor(module_symbols)
        visitor.visit(expr)
        return visitor.result


class ModuleSymbolCollector(ast.NodeVisitor):
    def __init__(self, module_asts: list[ModuleAST], root_path: Path) -> None:
        self.root = root_path
        self.module_asts = {ast.path: ast for ast in module_asts}
        self.symbols = list[ResolvedSymbol]()
        self.seen_files: set[Path] = set()

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        assert not node.level, "Relative imports not supported"
        assert node.module is not None, "Non relative imports must have module"

        base_path = node.module.replace(self.root_module_name, "").lstrip(".").replace(".", "/")
        for n in node.names:
            if n.name == "*":
                module_path = Path(self.root / (base_path + ".pyi"))
                module_name = self.root_module_name
                source = node.module
            else:
                module_path = Path(self.root / base_path / (n.name + ".pyi"))
                module_name = f"{node.module}.{n.name}"
                source = f"{node.module}.{n.name}"

            if not module_path.exists():
                module_name = self.root_module_name
                source = node.module
                self.symbols.append(ResolvedSymbol(module_name, n.name, source))
            else:
                self._collect_exported_symbols(module_path, module_name, source)

    def collect_module_symbols(self) -> None:
        self._collect_init_file_symbols()
        for path in self.root.rglob("*.pyi"):
            if path not in self.seen_files:
                self._collect_exported_symbols(path)

    def _collect_init_file_symbols(self) -> None:
        init_module = self.module_asts[self.root / "__init__.pyi"]
        init_tree = init_module.tree
        self.root_module_name = init_module.module_name

        self.visit(init_tree)
        self.seen_files.add(init_module.path)

    def _collect_exported_symbols(
        self, module_path: Path, module_name: str | None = None, source: str | None = None
    ) -> None:
        self.seen_files.add(module_path)
        module_ast = self.module_asts[module_path]
        module_name = module_name or module_ast.module_name
        source = source or module_name

        exported_symbol_visitor = _ExportedSymbolCollector()
        exported_symbol_visitor.visit(module_ast.tree)
        self.symbols.extend(
            [
                ResolvedSymbol(module_name, e, source)
                for e in exported_symbol_visitor.exported_symbols
            ]
        )


class _ExportedSymbolCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.is_explicit_export_defined = False
        self.exported_symbols = list[str]()

    @typing.override
    def visit_Assign(self, node: ast.Assign) -> None:
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "__all__"
        ):
            self.exported_symbols = []
            self.is_explicit_export_defined = True
            if isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        self.exported_symbols.append(elt.value)

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.is_explicit_export_defined:
            self.exported_symbols.append(node.name)


def _get_module_name_from_imports(name: str, module_symbols: list[ResolvedSymbol]) -> str | None:
    def _is_builtin_type(name: str) -> bool:
        return name in builtins.__dict__ and isinstance(builtins.__dict__[name], type)

    result = next(
        (f.module for f in module_symbols if name in (f.name, f.friendly_name, f.full_name)),
        None,
    )

    if result is None and _is_builtin_type(name):
        return "builtins"
    return result


@functools.cache
def build_stubs_classes() -> Mapping[str, ClassNode]:
    def _build_module_asts() -> list[ModuleAST]:
        stubs_root = STUBS_DIR.parent.resolve()
        module_asts = list[ModuleAST]()
        for path in stubs_root.rglob("*.pyi"):
            module_text = path.read_text(encoding="utf8")
            module_tree = ast.parse(module_text, filename=str(path))
            module_name = get_module_name_from_path(path, STUBS_DIR.parent)
            module_asts.append(ModuleAST(path=path, tree=module_tree, module_name=module_name))
        return module_asts

    def _build_module_symbols() -> list[ResolvedSymbol]:
        module_symbol_collector = ModuleSymbolCollector(module_asts, STUBS_DIR)
        module_symbol_collector.collect_module_symbols()
        return module_symbol_collector.symbols

    def _build_classes(module_ast: ModuleAST) -> list[ClassNode]:
        collector = ClassCollector(module_ast.module_name, module_symbols)
        collector.visit(module_ast.tree)
        return collector.classes

    module_asts = _build_module_asts()

    module_symbols = _build_module_symbols()

    classes = [c for module_ast in module_asts for c in _build_classes(module_ast)]

    return {c.name: c for c in classes}
