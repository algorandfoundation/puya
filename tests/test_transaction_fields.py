import ast
import json
from collections.abc import Mapping, Sequence

import attrs
import pytest

from puya.avm import TransactionType
from puya.awst.txn_fields import TxnField
from puyapy._stub_symtables import STUB_SYMTABLES
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.transaction.txn_fields import PYTHON_TXN_FIELDS
from tests import STUBS_DIR, VCS_ROOT

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
class _ProtocolProperty:
    name: str
    is_array: bool
    result_type: pytypes.PyType


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


def _parse_stub(name: str) -> ast.Module:
    path = STUBS_DIR / f"{name}.pyi"
    source = path.read_text("utf8")
    result = ast.parse(source, str(path))
    return result


_TxnProtocolData = Mapping[str, Mapping[str, _ProtocolProperty]]


@pytest.fixture(scope="session")
def transaction_protocols(builtins_registry: Mapping[str, pytypes.PyType]) -> _TxnProtocolData:
    fast = _parse_stub("_transaction")
    algopy_names = dict[str, str]()
    result = dict[str, Mapping[str, _ProtocolProperty]]()
    for stmt in fast.body:
        match stmt:
            case ast.Import(names=[ast.alias(name="typing", asname=None)]):
                pass
            case ast.ImportFrom(module=str(module), names=names, level=0):
                assert names is not None, "this test doesn't currently support import *"
                module_syms = STUB_SYMTABLES[module]
                for alias in names:
                    algopy_names[alias.asname or alias.name] = module_syms[alias.name].fullname
            case ast.ClassDef() as cdef:
                (base,) = cdef.bases
                assert _expand_name(base) == "typing.Protocol"
                result[cdef.name] = _parse_transaction_protocol_body(
                    cdef.body, algopy_names, builtins_registry
                )
            case other:
                raise TypeError(
                    f"test doesn't currently support this node type: {type(other).__name__}"
                )
    return result


def _parse_transaction_protocol_body(
    body: Sequence[ast.stmt],
    algopy_names: Mapping[str, str],
    registry: Mapping[str, pytypes.PyType],
) -> dict[str, _ProtocolProperty]:
    result = dict[str, _ProtocolProperty]()
    for stmt in body:
        assert isinstance(stmt, ast.FunctionDef), "expected function def / property"
        func_def = stmt
        match func_def.decorator_list, (func_def.args.posonlyargs + func_def.args.args)[1:]:
            case [[d], []] if _expand_name(d) == "property":
                is_array = False
            case [[], [ast.arg(arg="index")]]:
                is_array = True
            case _:
                raise AssertionError("expected a property getter or array index getter")
        assert func_def.returns is not None, "expected return type annotation"
        return_name = _expand_name(func_def.returns)
        if return_name in algopy_names:  # noqa: SIM401
            return_fullname = algopy_names[return_name]
        else:
            return_fullname = f"builtins.{return_name}"
        result_type = registry[return_fullname]
        assert func_def.name not in result
        result[func_def.name] = _ProtocolProperty(
            name=func_def.name, result_type=result_type, is_array=is_array
        )
    return result


def _expand_name(expr: ast.expr) -> str:
    match expr:
        case ast.Name(id=value):
            return value
        case ast.Attribute(value=base, attr=attr):
            base_name = _expand_name(base)
            return f"{base_name}.{attr}"
        case _:
            raise ValueError(f"cannot expand name for node type {type(expr).__name__}")


_ParamData = Mapping[str, Sequence[pytypes.PyType]]


@attrs.frozen(kw_only=True)
class _ITxnFieldSet:
    name: str
    init_params: _ParamData
    set_params: _ParamData


@pytest.fixture(scope="session")
def itxn_builders(builtins_registry: Mapping[str, pytypes.PyType]) -> Sequence[_ITxnFieldSet]:
    fast = _parse_stub("itxn")
    algopy_names = dict[str, str]()
    result = list[_ITxnFieldSet]()
    for stmt in fast.body:
        match stmt:
            case ast.ImportFrom(module=str(module), names=names, level=0) if module.startswith(
                "algopy"
            ):
                assert names is not None, "this test doesn't currently support import *"
                module_syms = STUB_SYMTABLES[module]
                for alias in names:
                    algopy_names[alias.asname or alias.name] = module_syms[alias.name].fullname
            case (
                ast.ClassDef(
                    name=name, bases=[ast.Subscript(value=ast.Name(id="_InnerTransaction"))]
                ) as cdef
            ) if name != "ABIApplicationCall":
                result.append(_parse_itxn_builder_body(cdef, algopy_names, builtins_registry))

    return result


def _parse_itxn_builder_body(
    cdef: ast.ClassDef,
    algopy_names: Mapping[str, str],
    registry: Mapping[str, pytypes.PyType],
) -> _ITxnFieldSet:
    init_params: _ParamData | None = None
    set_params: _ParamData | None = None
    for stmt in cdef.body:
        match stmt:
            case ast.FunctionDef(name="__init__"):
                init_params = _map_param_annotations(stmt.args, algopy_names, registry)
            case ast.FunctionDef(name="set"):
                set_params = _map_param_annotations(stmt.args, algopy_names, registry)
    assert init_params is not None, "missing __init__"
    assert set_params is not None, "missing set"
    return _ITxnFieldSet(name=cdef.name, init_params=init_params, set_params=set_params)


def _map_param_annotations(
    params: ast.arguments,
    algopy_names: Mapping[str, str],
    registry: Mapping[str, pytypes.PyType],
) -> Mapping[str, tuple[pytypes.PyType, ...]]:
    result = {}
    for arg in params.kwonlyargs:
        assert arg.annotation is not None
        arg_types = tuple(
            _annotation_to_pytype(registry, algopy_names, part)
            for part in _flatten_union(arg.annotation)
        )
        result[arg.arg] = arg_types
    return result


def _annotation_to_pytype(
    registry: Mapping[str, pytypes.PyType], algopy_names: Mapping[str, str], expr: ast.expr
) -> pytypes.PyType:
    match expr:
        case ast.Name(id=name):
            if name in algopy_names:  # noqa: SIM401
                qualified_name = algopy_names[name]
            else:
                qualified_name = f"builtins.{name}"
            return registry[qualified_name]
        case ast.Subscript(
            value=ast.Name(id="tuple"),
            slice=ast.Tuple(elts=[ast.expr() as element_type, ast.Constant(value=maybe_ellipsis)]),
        ) if maybe_ellipsis is Ellipsis:
            inner = _annotation_to_pytype(registry, algopy_names, element_type)
            return pytypes.VariadicTupleType(items=inner)
        case other:
            raise TypeError(f"couldn't transform annotation expression: {other}")


def _flatten_union(expr: ast.expr) -> list[ast.expr]:
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr):
        return _flatten_union(expr.left) + _flatten_union(expr.right)
    return [expr]


def test_python_txn_fields_complete() -> None:
    fields = set(TxnField)
    for py_txn_field in PYTHON_TXN_FIELDS.values():
        fields.remove(py_txn_field.field)
    assert not fields, "unmapped field(s)"


def test_python_itxn_fields_complete() -> None:
    fields = {
        tf
        for tf in TxnField
        if tf.is_inner_param and tf not in _INTENTIONALLY_OMITTED_INNER_TXN_FIELDS
    }
    for py_itxn_arg in PYTHON_ITXN_ARGUMENTS.values():
        fields.remove(py_itxn_arg.field)
    assert not fields, "unmapped field(s)"


def test_field_getters(transaction_protocols: _TxnProtocolData) -> None:
    unseen_fields = dict(PYTHON_TXN_FIELDS)
    for proto_fields in transaction_protocols.values():
        for field_name, field_data in proto_fields.items():
            py_txn_field = unseen_fields.pop(field_name)
            assert py_txn_field.type == field_data.result_type
            assert py_txn_field.field.is_array == field_data.is_array
    assert not unseen_fields, "some fields are not mapped"


def test_field_vs_argument_name_consistency() -> None:
    itxn_args = {
        (_MAPPED_INNER_TXN_FIELDS.get(params.field, params.field), name)
        for name, params in PYTHON_ITXN_ARGUMENTS.items()
    }
    txn_fields = {(f.field, name) for name, f in PYTHON_TXN_FIELDS.items()}
    bad_itxn_args = itxn_args - txn_fields
    assert not bad_itxn_args


def test_inner_transaction_field_setters(itxn_builders: Sequence[_ITxnFieldSet]) -> None:
    # one for each transaction type plus one "generic" type
    assert len(itxn_builders) == (len(TransactionType) + 1)

    seen_args = set[str]()
    for itxn_builder in itxn_builders:
        assert (
            itxn_builder.init_params == itxn_builder.set_params
        ), f"{itxn_builder.name} __init__ vs set field differences"
        seen_args |= itxn_builder.init_params.keys()
        for name, arg_types in itxn_builder.init_params.items():
            txn_field_param = PYTHON_ITXN_ARGUMENTS[name]
            assert set(txn_field_param.literal_overrides.keys()).issubset(arg_types)
            txn_field = txn_field_param.field
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
    # any difference is an error
    assert seen_args == PYTHON_ITXN_ARGUMENTS.keys()


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
