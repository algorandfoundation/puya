import ast
import builtins
import functools
import json
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
from puyapy.find_sources import ResolvedSource
from puyapy.import_analysis import _ImportCollector
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
    names: "list[str | TypeNode]" = attrs.field(factory=list)


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
    kind: ArgKind = ArgKind.ARG_POS
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
    properties: list[PropertyNode] = attrs.field(factory=list)
    functions: list[FunctionNode] = attrs.field(factory=list)
    bases: list[str] = attrs.field(factory=list)


def _classes_from_file(file_path: Path, root: Path) -> list[ClassNode]:
    """
    Parse a single .pyi file and return class names,
    and module level assignments which are (probably) type annotations.
    """
    module = get_module_name_from_path(file_path, root)
    text = file_path.read_text(encoding="utf8")
    tree = ast.parse(text, filename=str(file_path))
    visitor = _ImportCollector(ResolvedSource(path=file_path, module=module, base_dir=root))
    visitor.visit(tree)

    classes = []
    for stmt in tree.body:
        match stmt:
            case ast.ClassDef(name=class_name, bases=bases):
                # Create new class node with fully qualified name
                class_node = ClassNode(name=f"{module}.{class_name}")

                # Process base classes
                _process_base_classes(class_node, bases, visitor, module)

                # Process class body (properties and methods)
                _process_class_body(class_node, visitor, stmt.body)

                classes.append(class_node)

    return classes


def _expr_to_name(expr: ast.expr) -> str | None:
    """Extract a name from an AST expression."""
    match expr:
        case ast.Name(id=id):
            return id
        case ast.Subscript(value=val):
            return _expr_to_name(val)
        case ast.Constant(value=v) if isinstance(v, str):
            return v
        case _:
            return None


def _get_module_name_from_imports(name: str, visitor: _ImportCollector) -> str | None:
    result = next(
        (
            f.module
            for f in visitor.from_imports
            if any(n for n in f.names or [] if n.name == name)
        ),
        None,
    )

    if result is None and _is_builtin_type(name):
        return "builtins"
    return result


def _is_builtin_type(name: str) -> bool:
    """
    Checks if a given name, typically from an ast.Name node,
    corresponds to a built-in type in Python.
    """
    return name in builtins.__dict__ and isinstance(builtins.__dict__[name], type)


def _is_property_method(decorators: list[ast.expr]) -> bool:
    """Check if a method has property-related decorators."""
    return any(
        (isinstance(d, ast.Name) and d.id == "property")
        or (isinstance(d, ast.Attribute) and d.attr == "setter")
        for d in decorators
    )


def _is_deleter(decorators: list[ast.expr]) -> bool:
    """Check if a method is a property deleter."""
    return any(isinstance(d, ast.Attribute) and d.attr == "deleter" for d in decorators)


def _process_base_classes(
    class_node: ClassNode, bases: list[ast.expr], visitor: _ImportCollector, module: str
) -> None:
    """Process base classes and add them to the class node."""
    for base in bases:
        name = _expr_to_name(base)
        if name:
            # Find the module where this base class is imported from
            base_module = _get_module_name_from_imports(name, visitor)
            # Add the fully qualified base class name
            class_node.bases.append(f"{base_module or module}.{name}")


def _process_class_body(
    class_node: ClassNode, visitor: _ImportCollector, body: list[ast.stmt]
) -> None:
    """Process class body statements to extract properties and functions."""
    for stmt in body:
        match stmt:
            # Handle properties: annotations and assignments
            case (
                ast.AnnAssign(target=ast.Name(id=prop_name))
                | ast.Assign(targets=[ast.Name(id=prop_name)])
            ):
                class_node.properties.append(PropertyNode(name=prop_name))

            # Handle properties defined with @property decorator or property.setter
            case ast.FunctionDef(name=name, decorator_list=decorators) if _is_property_method(
                decorators
            ):
                class_node.properties.append(
                    PropertyNode(
                        name=name, type=_get_type_node(stmt.returns, visitor) or TypeNode()
                    )
                )

            # Handle regular methods (excluding property deleters)
            case ast.FunctionDef(
                name=func_name, args=args, returns=return_type, decorator_list=decorators
            ) if not _is_deleter(decorators):
                pos_args_len = len(args.posonlyargs) + len(args.args)
                pos_defaults_len = len(args.defaults)
                pos_defaults_cutoff = pos_args_len - pos_defaults_len

                arg_nodes = [
                    ArgNode(
                        name=a.arg,
                        type=_get_type_node(a.annotation, visitor) or TypeNode(),
                        kind=ArgKind.ARG_OPT if idx >= pos_defaults_cutoff else ArgKind.ARG_POS,
                    )
                    for idx, a in enumerate(args.posonlyargs + args.args)
                ]
                arg_nodes.extend(
                    [
                        ArgNode(
                            name=a.arg,
                            type=_get_type_node(a.annotation, visitor) or TypeNode(),
                            kind=ArgKind.ARG_NAMED_OPT
                            if args.kw_defaults[idx] is not None
                            else ArgKind.ARG_NAMED,
                        )
                        for idx, a in enumerate(args.kwonlyargs)
                    ]
                )
                class_node.functions.append(
                    FunctionNode(
                        name=func_name,
                        args=arg_nodes,
                        return_type=_get_type_node(return_type, visitor) or TypeNode(),
                    )
                )


def _get_type_node(type_expr: ast.expr | None, visitor: _ImportCollector) -> TypeNode | None:
    names: list[str | TypeNode] = ["None"]
    is_array = False
    if type_expr:
        match type_expr:
            case ast.Constant(value=None):
                pass
            case ast.Name(id=id):
                module = _get_module_name_from_imports(id, visitor)
                names = [f"{module}.{id}" if module else id]
            case ast.Subscript(value=ast.Name(id="Iterator" | "Iterable"), slice=ast.Name(id=id)):
                is_array = True
                module = _get_module_name_from_imports(id, visitor)
                names = [f"{module}.{id}" if module else id]
            case ast.Subscript(value=ast.Name(id="Iterator" | "Iterable"), slice=slice_value):
                is_array = True
                t = _get_type_node(slice_value, visitor)
                names = [t] if t else []
            case ast.Attribute(value=ast.Name(id="typing"), attr="Self"):
                names = ["typing.Self"]
            case ast.Attribute(value=ast.Name(id=id), attr=attr):
                names = [f"{id}.{attr}"]
            case ast.BinOp(left=left, right=right, op=ast.BitOr()):
                left_node = _get_type_node(left, visitor)
                right_node = _get_type_node(right, visitor)
                names = [
                    *([left_node] if left_node else []),
                    *([right_node] if right_node else []),
                ]
                is_array = (left_node.is_array if left_node else False) and (
                    right_node.is_array if right_node else False
                )
            case ast.Subscript(slice=ast.Tuple(elts=elts)):
                is_array = True
                names = []
                for elt in elts:
                    t = _get_type_node(elt, visitor)
                    names.extend([t] if t else [])
            case ast.Constant(value=value) if value is Ellipsis:
                return None
            case _:
                pass
    return TypeNode(names=names, is_array=is_array)


@functools.cache
def _build_stubs() -> list[ClassNode]:
    stubs_root = STUBS_DIR.parent.resolve()
    classes = []
    for path in stubs_root.rglob("*.pyi"):
        classes.extend(_classes_from_file(path, stubs_root))
    return classes


def _get_type_infos(
    type_names: Iterable[str],
) -> Iterable[ClassNode]:
    result = _build_stubs()

    for type_name in type_names:
        match = next((c for c in result if c.name in (type_name)), None)
        if not match:
            continue

        properties = match.properties
        functions = match.functions

        # Extend properties with base class properties
        for bases in _get_type_infos(match.bases):
            properties.extend(bases.properties)
            functions.extend(bases.functions)
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
        attributes = [p.name for p in type_info.properties]
        attributes.extend(
            [f.name for f in type_info.functions if f.name.startswith("__") is False]
        )
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
            func_def = next(f for f in type_info.functions if f.name == member)
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
        attributes = [p.name for p in type_info.properties]
        attributes.extend(
            [f.name for f in type_info.functions if f.name.startswith("__") is False]
        )
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
        if len(node.names) > 1:
            t: pytypes.PyType = pytypes.UnionType(
                types=[
                    _get_pytype_for_name(t) if isinstance(t, str) else _get_pytype_for_node(t)
                    for t in node.names
                ],
                source_location=_FAKE_SOURCE_LOCATION,
            )
        else:
            t = (
                _get_pytype_for_name(node.names[0])
                if isinstance(node.names[0], str)
                else _get_pytype_for_node(node.names[0])
            )
        return pytypes.VariadicTupleType(t) if node.is_array else t

    for type_info_1 in _get_type_infos(txn_types):
        type_nodes = [
            (
                p.name,
                FieldType(is_array=p.type.is_array, field_type=_get_pytype_for_node(p.type)),
            )
            for p in type_info_1.properties
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
                for f in type_info_1.functions
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

    for type_info_2 in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        for member in ("__init__", "set"):
            func_def = next(f for f in type_info_2.functions if f.name == member)
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
