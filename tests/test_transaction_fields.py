import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import attrs
import pytest

from puya.awst.txn_fields import TxnField
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.transaction.txn_fields import PYTHON_TXN_FIELDS
from tests import VCS_ROOT
from tests.utils.stubs_ast import ClassNode, FunctionNode, TypeNode, build_stubs_classes

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


def _get_type_infos(
    type_names: Iterable[str],
) -> Iterable[ClassNode]:
    result = build_stubs_classes()

    for type_name in type_names:
        match = result[type_name]

        # Extend properties with base class properties
        for bases in _get_type_infos(match.bases):
            match.properties.update(bases.properties)
            match.functions.update(bases.functions)

        yield match


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

    for type_info in _get_type_infos(txn_types):
        type_nodes = [
            (p.name, p.type.is_array, _type_to_pytype(p.type, builtins_registry))
            for p in type_info.properties.values()
        ] + [
            (
                f.name,
                f.return_type.is_array or len(f.args) > 1,
                _type_to_pytype(f.return_type, builtins_registry),
            )
            for f in type_info.functions.values()
            if f.name.startswith("__") is False
        ]

        for type_node in type_nodes:
            seen_fields.add(type_node[0])
            txn_field_data = PYTHON_TXN_FIELDS[type_node[0]]

            assert txn_field_data.field.is_array == type_node[1]
            assert txn_field_data.type == type_node[2]

    # add fields that are arguments
    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        for member in ("__init__", "set"):
            func_def = type_info.functions[member]
            func_type = _func_to_pytype(func_def, builtins_registry)
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


def _type_to_pytype(
    node: TypeNode, builtins_registry: Mapping[str, pytypes.PyType]
) -> pytypes.PyType:
    def _get_pytype_for_name(name: str) -> pytypes.PyType:
        return next(e for e in builtins_registry.values() if str(e) == name or e.name == name)

    def _get_pytype_for_node(node: TypeNode) -> pytypes.PyType:
        if len(node.types) == 0:
            return pytypes.NoneType

        mapped_types = [
            _get_pytype_for_name(a) if isinstance(a, str) else _get_pytype_for_node(a)
            for a in node.types
        ]

        t = (
            pytypes.UnionType(types=mapped_types, source_location=_FAKE_SOURCE_LOCATION)
            if len(mapped_types) > 1
            else mapped_types[0]
        )

        return pytypes.VariadicTupleType(t) if node.is_array else t

    return _get_pytype_for_node(node)


def _func_to_pytype(
    func_def: FunctionNode, builtins_registry: Mapping[str, pytypes.PyType]
) -> pytypes.PyType:
    return pytypes.FuncType(
        name=func_def.name,
        args=[
            pytypes.FuncArg(
                name=a.name,
                type=_type_to_pytype(a.type, builtins_registry),
                kind=a.kind,  # type: ignore[arg-type]
            )
            for a in func_def.args
        ],
        ret_type=_type_to_pytype(func_def.return_type, builtins_registry),
    )
