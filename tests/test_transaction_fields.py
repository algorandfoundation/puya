import ast
import builtins
import functools
import itertools
import json
import typing
from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path

import attrs
import pytest

from puya.awst.txn_fields import TxnField
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.transaction.txn_fields import PYTHON_TXN_FIELDS
from tests import STUBS_DIR, VCS_ROOT
from tests.utils import get_module_name_from_path

# the need to use approval / clear_state pages is abstracted away by
# allowing a tuple of pages in the stubs layer
_MAPPED_INNER_TXN_FIELDS = {
    TxnField.ApprovalProgramPages: TxnField.ApprovalProgram,
    TxnField.ClearStateProgramPages: TxnField.ClearStateProgram,
}
_INTENTIONALLY_OMITTED_INNER_TXN_FIELDS = {
    *_MAPPED_INNER_TXN_FIELDS.values(),
    # only allow enum version of type
    TxnField.Type,
}


@attrs.frozen
class FieldType:
    is_array: bool
    field_type: pytypes.PyType


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
class ResolvedSymbol:
    module: str
    name: str
    source: str

    @property
    def full_name(self) -> str:
        return f"{self.module}.{self.name}"

    @property
    def full_source_name(self) -> str:
        return f"{self.source}.{self.name}"


class ClassCollector(ast.NodeVisitor):
    """Collect top-level classes and build ClassNode instances."""

    def __init__(self, module: str, module_symbols: list[ResolvedSymbol]) -> None:
        self.module = module
        self.module_symbols = module_symbols
        self.classes: list[ClassNode] = []
        self.class_attribute_collector = _ClassAttributeCollector(module_symbols)

    @typing.override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_node = ClassNode(name=f"{self.module}.{node.name}")

        # Extend the class_node with collected bases
        base_class_collector = _BaseClassCollector(self.module, self.module_symbols)
        base_class_collector.visit(node)
        class_node.bases.extend(base_class_collector.result)

        # Extend the class_node with collected members
        self.class_attribute_collector.visit(node)
        class_node.properties.update(
            {p.name: p for p in self.class_attribute_collector.properties}
        )
        class_node.functions.update({f.name: f for f in self.class_attribute_collector.functions})

        self.classes.append(class_node)


class _BaseClassCollector(ast.NodeVisitor):
    def __init__(self, module: str, module_symbols: list[ResolvedSymbol]) -> None:
        self.bases: list[str] = []
        self.module = module
        self.module_symbols = module_symbols

    @property
    def result(self) -> list[str]:
        def _get_full_name(name: str) -> str:
            base_module = _get_module_name_from_imports(name, self.module_symbols)
            return f"{base_module or self.module}.{name}"

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
        self.properties: list[PropertyNode] = []
        self.functions: list[FunctionNode] = []
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
                    type=_get_type_node(node.annotation, self.module_symbols) or TypeNode(),
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
                    type=_get_type_node(node.returns, self.module_symbols) or TypeNode(),
                )
            )
            return

        # Regular function/method
        args = node.args
        pos_args_len = len(args.posonlyargs) + len(args.args)
        pos_defaults_len = len(args.defaults)
        pos_defaults_cutoff = pos_args_len - pos_defaults_len

        arg_nodes = [
            ArgNode(
                name=a.arg,
                type=_get_type_node(a.annotation, self.module_symbols) or TypeNode(),
                kind=ArgKind.ARG_OPT if idx >= pos_defaults_cutoff else ArgKind.ARG_POS,
            )
            for idx, a in enumerate(args.posonlyargs + args.args)
        ]

        # Keyword-only args
        arg_nodes.extend(
            [
                ArgNode(
                    name=a.arg,
                    type=_get_type_node(a.annotation, self.module_symbols) or TypeNode(),
                    kind=ArgKind.ARG_NAMED_OPT
                    if args.kw_defaults[idx] is not None
                    else ArgKind.ARG_NAMED,
                )
                for idx, a in enumerate(args.kwonlyargs)
            ]
        )

        self.functions.append(
            FunctionNode(
                name=node.name,
                args=arg_nodes,
                return_type=_get_type_node(node.returns, self.module_symbols) or TypeNode(),
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


class _TypeExprVisitor(ast.NodeVisitor):
    """Visitor that maps a type expression AST into a TypeNode.

    This preserves the original pattern-matching behavior from the
    procedural implementation but uses the NodeVisitor pattern so the
    code is easier to extend.
    """

    def __init__(self, module_symbols: list[ResolvedSymbol]) -> None:
        self.module_symbols = module_symbols
        self.types: list[str | TypeNode] = []
        self.is_array = False

    @property
    def result(self) -> TypeNode | None:
        if len(self.types) == 0:
            return None
        return TypeNode(types=self.types, is_array=self.is_array)

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
            names: list[str | TypeNode] = []
            if left:
                names.append(left)
            if right:
                names.append(right)
            self.types = names or []
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
            elts: list[ast.expr] = node.slice.elts
            names: list[str | TypeNode] = []
            for elt in elts:
                t = self._visit_expr(elt, self.module_symbols)
                if t:
                    names.append(t)
            self.types = names or []

    def _visit_expr(self, expr: ast.expr, module_symbols: list[ResolvedSymbol]) -> TypeNode | None:
        visitor = _TypeExprVisitor(module_symbols)
        visitor.visit(expr)
        return visitor.result


class ModuleSymbolCollector(ast.NodeVisitor):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.symbols: dict[str, list[ResolvedSymbol]] = {}
        self.seen_files: set[Path] = set()

    @typing.override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            return
        module = self.root_module_name
        from_name = node.module
        # Process each imported name separately. For a star import we map
        # the module itself to the exported symbols; for `from X import Y`
        # we map `X.Y` to the exported symbols from the corresponding
        # stub file (or record the name if the stub file doesn't exist).
        base_path = from_name.replace(self.root_module_name, "").lstrip(".").replace(".", "/")
        for n in node.names:
            if not isinstance(n, ast.alias):
                continue

            symbols: list[ResolvedSymbol] = []
            if n.name == "*":
                module_path = Path(self.root / (base_path + ".pyi"))
                module = self.root_module_name
                source = from_name
            else:
                module_path = Path(self.root / base_path / (n.name + ".pyi"))
                module = f"{from_name}.{n.name}"
                source = f"{from_name}.{n.name}"

            if not module_path.exists():
                # If the module path doesn't exist in stubs, record the name
                # as-is so callers know which symbol was referenced.
                module = self.root_module_name
                source = from_name
                symbols.append(ResolvedSymbol(module, n.name, source))
            else:
                exported_symbols = self._collect_exported_symbols(module_path, module, source)
                symbols.extend(exported_symbols)

            # Merge symbols for this module; multiple imports shouldn't clobber
            # previously-recorded entries for the same key.
            self.symbols.setdefault(module, []).extend(symbols)

    def collect_module_symbols(self) -> None:
        self._collect_init_file_symbols()
        for path in self.root.rglob("*.pyi"):
            if path not in self.seen_files:
                symbols = self._collect_exported_symbols(path)
                if len(symbols) > 0:
                    self.symbols.setdefault(symbols[0].module, []).extend(symbols)

    def _collect_init_file_symbols(self) -> dict[str, list[ResolvedSymbol]]:
        init_file_path = self.root / "__init__.pyi"
        init_text = init_file_path.read_text(encoding="utf8")
        init_tree = ast.parse(init_text, filename=str(init_file_path))
        self.root_module_name = get_module_name_from_path(init_file_path, self.root.parent)

        self.visit(init_tree)
        self.seen_files.add(init_file_path)
        return self.symbols

    def _collect_exported_symbols(
        self, module_path: Path, module: str | None = None, source: str | None = None
    ) -> list[ResolvedSymbol]:
        self.seen_files.add(module_path)
        module_text = module_path.read_text(encoding="utf8")
        module_tree = ast.parse(module_text, filename=str(module_path))
        exported_symbol_visitor = _ExportedSymbolCollector()
        exported_symbol_visitor.visit(module_tree)
        module = module or get_module_name_from_path(module_path, self.root.parent)
        source = source or module
        return [
            ResolvedSymbol(module, e, source) for e in exported_symbol_visitor.exported_symbols
        ]


class _ExportedSymbolCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.is_explicit_export_defined = False
        self.exported_symbols: list[str] = []

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
        (f.module for f in module_symbols if name in (f.name, f.full_name, f.full_source_name)),
        None,
    )

    if result is None and _is_builtin_type(name):
        return "builtins"
    return result


def _get_type_node(
    type_expr: ast.expr | None, module_symbols: list[ResolvedSymbol]
) -> TypeNode | None:
    if type_expr is None:
        return None
    type_expr_visitor = _TypeExprVisitor(module_symbols)
    type_expr_visitor.visit(type_expr)
    return type_expr_visitor.result


def _classes_from_file(
    file_path: Path, root: Path, module_symbols: list[ResolvedSymbol]
) -> list[ClassNode]:
    """Parse a single .pyi file and return top-level ClassNode objects.

    This uses an ast.NodeVisitor (ClassCollector) to collect only top-level
    classes so nested/inner classes are ignored (preserving previous behavior).
    """

    module = get_module_name_from_path(file_path, root)
    text = file_path.read_text(encoding="utf8")
    tree = ast.parse(text, filename=str(file_path))

    collector = ClassCollector(module, module_symbols)
    collector.visit(tree)
    return collector.classes


@functools.cache
def _build_stubs() -> Mapping[str, ClassNode]:
    module_symbol_collector = ModuleSymbolCollector(STUBS_DIR)
    module_symbol_collector.collect_module_symbols()
    module_symbols = list(itertools.chain.from_iterable(module_symbol_collector.symbols.values()))

    stubs_root = STUBS_DIR.parent.resolve()
    classes = []
    for path in stubs_root.rglob("*.pyi"):
        classes.extend(_classes_from_file(path, stubs_root, module_symbols))
    return {c.name: c for c in classes}


def _get_type_infos(
    type_names: Iterable[str],
) -> Iterable[ClassNode]:
    result = _build_stubs()

    for type_name in type_names:
        match = result[type_name]
        properties = match.properties
        functions = match.functions

        # Extend properties with base class properties
        for bases in _get_type_infos(match.bases):
            properties.update(bases.properties)
            functions.update(bases.functions)
        yield ClassNode(
            name=match.name,
            properties=properties,
            functions=functions,
        )


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


@pytest.mark.parametrize(
    "group_transaction_type", [t.name for t in pytypes.GroupTransactionTypes.values()]
)
def test_group_transaction_members(group_transaction_type: str) -> None:
    gtxn_types = [group_transaction_type, pytypes.GroupTransactionBaseType.name]
    for type_info in _get_type_infos(gtxn_types):
        attributes = list(type_info.properties)
        attributes.extend([f for f in type_info.functions if f.startswith("__") is False])
        unknown = sorted(set(attributes) - PYTHON_TXN_FIELDS.keys())
        assert not unknown, f"{type_info.name}: Unknown TxnField members: {unknown}"


def test_field_vs_argument_name_consistency() -> None:
    itxn_args = {
        (_MAPPED_INNER_TXN_FIELDS.get(params.field, params.field), name)
        for name, params in PYTHON_ITXN_ARGUMENTS.items()
    }
    txn_fields = {(f.field, name) for name, f in PYTHON_TXN_FIELDS.items()}
    bad_itxn_args = itxn_args - txn_fields
    assert not bad_itxn_args


def test_inner_transaction_field_setters() -> None:
    unmapped = {
        tf for tf in TxnField if tf.is_inner_param
    } - _INTENTIONALLY_OMITTED_INNER_TXN_FIELDS
    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        init_args: set[str] | None = None
        for member in ("__init__", "set"):
            func_def = type_info.functions[member]
            # Extract arg names from the FunctionNode's args list
            arg_names = {a.name for a in func_def.args}
            arg_names.discard("self")
            unknown = sorted(arg_names - PYTHON_ITXN_ARGUMENTS.keys())
            assert not unknown, f"{type_info.name}: Unknown TxnField param members: {unknown}"
            unmapped -= {
                PYTHON_ITXN_ARGUMENTS[arg_name].field
                for arg_name in arg_names
                if arg_name not in unknown
            }

            if init_args is None:
                init_args = arg_names
            else:
                difference = init_args.symmetric_difference(arg_names)
                assert not difference, f"{type_info.name}.{member} field difference: {difference}"
    assert not unmapped, f"Unmapped inner param fields: {sorted(f.immediate for f in unmapped)}"


@pytest.mark.parametrize(
    "inner_transaction_type", [t.name for t in pytypes.InnerTransactionResultTypes.values()]
)
def test_inner_transaction_members(inner_transaction_type: str) -> None:
    for type_info in _get_type_infos([inner_transaction_type]):
        attributes = list(type_info.properties)
        attributes.extend([f for f in type_info.functions if f.startswith("__") is False])
        unknown = sorted(set(attributes) - PYTHON_TXN_FIELDS.keys())
        assert not unknown, f"{type_info.name}: Unknown TxnField members: {unknown}"


_FAKE_SOURCE_LOCATION = SourceLocation(file=Path(__file__).resolve(), line=1, end_line=1)


def test_txn_fields(builtins_registry: Mapping[str, pytypes.PyType]) -> None:
    # collect all fields that are protocol members
    txn_types = [t.name for t in pytypes.GroupTransactionTypes.values()]
    txn_types.append(pytypes.GroupTransactionBaseType.name)
    txn_types.extend(t.name for t in pytypes.InnerTransactionResultTypes.values())
    seen_fields = set[str]()

    def _get_pytype_for_name(name: str) -> pytypes.PyType:
        return next(e for e in builtins_registry.values() if str(e) == name or e.name == name)

    def _get_pytype_for_node(node: TypeNode) -> pytypes.PyType:
        if len(node.types) == 0:
            return pytypes.NoneType
        if len(node.types) > 1:
            t: pytypes.PyType = pytypes.UnionType(
                types=[
                    _get_pytype_for_name(t) if isinstance(t, str) else _get_pytype_for_node(t)
                    for t in node.types
                ],
                source_location=_FAKE_SOURCE_LOCATION,
            )
        else:
            t = (
                _get_pytype_for_name(node.types[0])
                if isinstance(node.types[0], str)
                else _get_pytype_for_node(node.types[0])
            )
        return pytypes.VariadicTupleType(t) if node.is_array else t

    for type_info in _get_type_infos(txn_types):
        type_nodes = [
            (
                p.name,
                FieldType(is_array=p.type.is_array, field_type=_get_pytype_for_node(p.type)),
            )
            for p in type_info.properties.values()
        ]
        type_nodes.extend(
            [
                (
                    f.name,
                    FieldType(
                        is_array=f.return_type.is_array or len(f.args) > 1,
                        field_type=_get_pytype_for_node(f.return_type),
                    ),
                )
                for f in type_info.functions.values()
                if f.name.startswith("__") is False
            ]
        )
        for type_node in type_nodes:
            seen_fields.add(type_node[0])
            txn_field_data = PYTHON_TXN_FIELDS[type_node[0]]
            field_type = FieldType(
                is_array=txn_field_data.field.is_array, field_type=txn_field_data.type
            )
            member_type = type_node[1]
            assert field_type == member_type

    # add fields that are arguments

    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        for member in ("__init__", "set"):
            func_def = type_info.functions[member]
            func_type = pytypes.FuncType(
                name=func_def.name,
                args=[
                    pytypes.FuncArg(
                        name=a.name,
                        type=_get_pytype_for_node(a.type),
                        kind=a.kind,  # type: ignore[arg-type]
                    )
                    for a in func_def.args
                ],
                ret_type=_get_pytype_for_node(func_def.return_type),
            )
            assert isinstance(func_type, pytypes.FuncType)
            for arg in func_type.args:
                assert arg.name is not None
                if arg.name == "self":
                    continue
                seen_fields.add(arg.name)
                txn_field_param = PYTHON_ITXN_ARGUMENTS[arg.name]
                txn_field = txn_field_param.field
                if isinstance(arg.type, pytypes.UnionType):
                    arg_types = arg.type.types
                else:
                    arg_types = (arg.type,)
                assert set(txn_field_param.literal_overrides.keys()).issubset(arg_types)

                if txn_field.is_array:
                    arg_types = tuple(
                        vt.items for vt in arg_types if isinstance(vt, pytypes.VariadicTupleType)
                    )
                if txn_field_param.auto_serialize_bytes:
                    assert arg_types == (pytypes.ObjectType,)
                else:
                    non_literal_arg_types = {
                        at for at in arg_types if not isinstance(at, pytypes.LiteralOnlyType)
                    }
                    assert non_literal_arg_types == {
                        txn_field_param.type,
                        *txn_field_param.additional_types,
                    }

    # anything missing is an error
    missing_fields = sorted(PYTHON_TXN_FIELDS.keys() - seen_fields)
    assert not missing_fields, f"Txn Fields not mapped: {missing_fields}"


def test_mismatched_langspec_txn_fields() -> None:
    langspec_path = VCS_ROOT / "langspec.puya.json"
    langspec = json.loads(langspec_path.read_text(encoding="utf8"))
    arg_enums = langspec["arg_enums"]
    all_txn_fields = {field["name"] for field in arg_enums["txn"]}
    txn_array_fields = {field["name"] for field in arg_enums["txna"]}
    txn_single_fields = all_txn_fields - txn_array_fields
    inner_txn_fields = {field["name"] for field in arg_enums["itxn_field"]}

    assert not _set_difference(
        all_txn_fields, [f.immediate for f in TxnField]
    ), "txn field mismatch"

    assert not _set_difference(
        txn_single_fields, [f.immediate for f in TxnField if not f.is_array]
    ), "single txn field mismatch"

    assert not _set_difference(
        txn_array_fields, [f.immediate for f in TxnField if f.is_array]
    ), "array txn field mismatch"

    assert not _set_difference(
        inner_txn_fields, [f.immediate for f in TxnField if f.is_inner_param]
    ), "inner txn field mismatch"


def _set_difference(expected: set[str], actual: list[str]) -> list[str]:
    return list(expected.symmetric_difference(actual))
