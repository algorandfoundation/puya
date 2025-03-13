import json
from collections.abc import Iterable, Mapping
from pathlib import Path

import attrs
import mypy.nodes
import mypy.types
import pytest

from puya.awst.txn_fields import TxnField
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.context import type_to_pytype
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.transaction.txn_fields import PYTHON_TXN_FIELDS
from tests import EXAMPLES_DIR, VCS_ROOT
from tests.utils import get_awst_cache

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


def _get_type_infos(type_names: Iterable[str]) -> Iterable[mypy.nodes.TypeInfo]:
    awst_cache = get_awst_cache(EXAMPLES_DIR)

    for type_name in type_names:
        module_id, symbol_name = type_name.rsplit(".", maxsplit=1)
        module = awst_cache.parse_result.ordered_modules[module_id].node

        symbol = module.names[symbol_name]
        node = symbol.node
        assert isinstance(node, mypy.nodes.TypeInfo), f"{type_name} not found in {module}"
        yield node


@pytest.fixture(scope="session")
def builtins_registry() -> Mapping[str, pytypes.PyType]:
    return pytypes.builtins_registry()


def test_group_transaction_members() -> None:
    gtxn_types = [t.name for t in pytypes.GroupTransactionTypes.values()]
    gtxn_types.append(pytypes.GroupTransactionBaseType.name)
    for type_info in _get_type_infos(gtxn_types):
        unknown = sorted(set(type_info.protocol_members) - PYTHON_TXN_FIELDS.keys())
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


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
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            arg_names = {a for a in func_def.arg_names if a is not None}
            arg_names.remove("self")
            unknown = sorted(arg_names - PYTHON_ITXN_ARGUMENTS.keys())
            assert not unknown, f"{type_info.fullname}: Unknown TxnField param members: {unknown}"
            unmapped -= {
                PYTHON_ITXN_ARGUMENTS[arg_name].field
                for arg_name in arg_names
                if arg_name not in unknown
            }

            if init_args is None:
                init_args = arg_names
            else:
                difference = init_args.symmetric_difference(arg_names)
                assert (
                    not difference
                ), f"{type_info.fullname}.{member} field difference: {difference}"
    assert not unmapped, f"Unmapped inner param fields: {sorted(f.immediate for f in unmapped)}"


def test_inner_transaction_members() -> None:
    for type_info in _get_type_infos(t.name for t in pytypes.InnerTransactionResultTypes.values()):
        unknown = sorted(set(type_info.protocol_members) - PYTHON_TXN_FIELDS.keys())
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


_FAKE_SOURCE_LOCATION = SourceLocation(file=Path(__file__).resolve(), line=1)


def test_txn_fields(builtins_registry: Mapping[str, pytypes.PyType]) -> None:
    # collect all fields that are protocol members
    txn_types = [t.name for t in pytypes.GroupTransactionTypes.values()]
    txn_types.append(pytypes.GroupTransactionBaseType.name)
    txn_types.extend(t.name for t in pytypes.InnerTransactionResultTypes.values())
    seen_fields = set[str]()
    invalid_types = ""
    for type_info in _get_type_infos(txn_types):
        for member in type_info.protocol_members:
            seen_fields.add(member)
            txn_field_data = PYTHON_TXN_FIELDS[member]
            field_type = FieldType(
                is_array=txn_field_data.field.is_array, field_type=txn_field_data.type
            )
            member_mypy_type = type_info[member].type
            assert member_mypy_type is not None, f"Expected {type_info}.{member} to have a type"
            member_type = _member_to_field_type(builtins_registry, member_mypy_type)
            assert field_type == member_type

    # add fields that are arguments
    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        for member in ("__init__", "set"):
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            assert func_def.type is not None
            func_type = type_to_pytype(
                builtins_registry, func_def.type, source_location=_FAKE_SOURCE_LOCATION
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

    # any invalid_types is an error
    assert not invalid_types, f"Invalid field types: {invalid_types}"


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


def _member_to_field_type(
    builtins_registry: Mapping[str, pytypes.PyType], typ: mypy.types.Type
) -> FieldType:
    is_array = False
    if isinstance(typ, mypy.types.CallableType):
        is_array = len(typ.arg_names) > 1
        typ = typ.ret_type

    field_type = type_to_pytype(builtins_registry, typ, source_location=_FAKE_SOURCE_LOCATION)

    return FieldType(is_array=is_array, field_type=field_type)
