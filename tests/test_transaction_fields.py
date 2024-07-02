import json
import typing
from collections.abc import Iterable, Mapping, Sequence

import attrs
import mypy.nodes
import mypy.types
import pytest
from puya.awst import wtypes
from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.context import type_to_pytype
from puya.awst_build.eb.transaction import get_argument_python_name, get_field_python_name

from tests import EXAMPLES_DIR, VCS_ROOT
from tests.utils import get_awst_cache

_ALL_PYTHON_TXN_FIELD_NAMES = {get_field_python_name(f): f for f in TxnField}
_INNER_TRANSACTION_PYTHON_TXN_FIELD_NAMES = {
    arg_name
    for f in TxnField
    if f.is_inner_param and (arg_name := get_argument_python_name(f)) is not None
}
# the need to use approval / clear_state pages is abstracted away by
# allowing a tuple of pages in the stubs layer
_MAPPED_INNER_TXN_FIELDS = {
    "approval_program": "approval_program_pages",
    "clear_state_program": "clear_state_program_pages",
}
_INTENTIONALLY_OMITTED_INNER_TXN_FIELDS = {
    *_MAPPED_INNER_TXN_FIELDS.keys(),
    # only allow enum version of type
    "type_bytes",
}


@attrs.frozen(str=False)
class FieldType:
    is_array: bool
    field_types: Sequence[wtypes.WType | type[wtypes.WType]]

    def is_compatible(self, other: typing.Self) -> bool:
        return self.is_array == other.is_array and set(self.field_types).issubset(
            other.field_types
        )

    def __str__(self) -> str:
        types = " | ".join(
            t.name if isinstance(t, wtypes.WType) else t.__name__ for t in self.field_types
        )
        if self.is_array:
            return f"tuple[{types}, ...]"
        return types


def _get_type_infos(type_names: Iterable[str]) -> Iterable[mypy.nodes.TypeInfo]:
    awst_cache = get_awst_cache(EXAMPLES_DIR)

    for type_name in type_names:
        module_id, symbol_name = type_name.rsplit(".", maxsplit=1)
        module = awst_cache.context.parse_result.manager.modules[module_id]

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
        unknown = sorted(set(type_info.protocol_members) - _ALL_PYTHON_TXN_FIELD_NAMES.keys())
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


def test_inner_transaction_field_setters() -> None:
    unmapped = _INNER_TRANSACTION_PYTHON_TXN_FIELD_NAMES - _INTENTIONALLY_OMITTED_INNER_TXN_FIELDS
    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        init_args: set[str] | None = None
        for member in ("__init__", "set"):
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            arg_names = {a for a in func_def.arg_names if a is not None}
            arg_names.remove("self")
            unknown = sorted(arg_names - _INNER_TRANSACTION_PYTHON_TXN_FIELD_NAMES)
            assert not unknown, f"{type_info.fullname}: Unknown TxnField param members: {unknown}"
            unmapped -= arg_names

            if init_args is None:
                init_args = arg_names
            else:
                difference = init_args.symmetric_difference(arg_names)
                assert (
                    not difference
                ), f"{type_info.fullname}.{member} field difference: {difference}"
    assert not unmapped, f"Unmapped inner param fields: {sorted(unmapped)}"


def test_inner_transaction_members() -> None:
    for type_info in _get_type_infos(t.name for t in pytypes.InnerTransactionResultTypes.values()):
        unknown = sorted(set(type_info.protocol_members) - _ALL_PYTHON_TXN_FIELD_NAMES.keys())
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


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
            txn_field = _ALL_PYTHON_TXN_FIELD_NAMES[member]
            member_mypy_type = type_info[member].type
            assert member_mypy_type is not None, f"Expected {type_info}.{member} to have a type"
            member_type = _member_to_field_type(member_mypy_type)
            field_type = FieldType(
                is_array=txn_field.is_array,
                field_types=(txn_field.wtype,),  # member types are invariant
            )
            if not member_type.is_compatible(field_type):
                invalid_types += (
                    f"Invalid member type for {type_info.fullname}.{member}."
                    f" TxnField: {txn_field.wtype}, Stubs: {member_type}\n"
                )

    # add fields that are arguments
    for type_info in _get_type_infos(
        t.name for t in pytypes.InnerTransactionFieldsetTypes.values()
    ):
        for member in ("__init__", "set"):
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            assert func_def.type is not None
            func_type = type_to_pytype(builtins_registry, func_def.type, source_location=None)
            assert isinstance(func_type, pytypes.FuncType)
            for arg in func_type.args:
                assert arg.name is not None
                if arg.name == "self":
                    continue
                seen_fields.add(arg.name)
                txn_field = _ALL_PYTHON_TXN_FIELD_NAMES[
                    _MAPPED_INNER_TXN_FIELDS.get(arg.name, arg.name)
                ]
                # if txn_field != TxnField.ApplicationArgs:
                txn_field_pytype = pytypes.from_basic_wtype(txn_field.wtype)
                arg_types = arg.types
                if txn_field.is_array:
                    arg_types = [
                        vt.items for vt in arg_types if isinstance(vt, pytypes.VariadicTupleType)
                    ]
                for stub_arg_typ in arg_types:
                    if stub_arg_typ == pytypes.ObjectType:
                        # escape hatch
                        break
                    if stub_arg_typ == txn_field_pytype or txn_field_pytype in stub_arg_typ.bases:
                        break
                else:
                    invalid_types += (
                        f"Invalid arg type for {type_info.fullname}.{member}({arg.name})."
                        f" field: {txn_field!r},"
                        f" implied: {txn_field_pytype},"
                        f" argument type: {' | '.join(map(str, arg.types))}\n"
                    )

    # anything missing is an error
    missing_fields = sorted(_ALL_PYTHON_TXN_FIELD_NAMES.keys() - seen_fields)
    assert not missing_fields, f"Txn Fields not mapped: {missing_fields}"

    # any invalid_types is an error
    assert not invalid_types, f"Invalid field types: {invalid_types}"


def test_mismatched_langspec_txn_fields() -> None:
    langspec_path = VCS_ROOT / "langspec.puya.json"
    langspec = json.loads(langspec_path.read_text())
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


def _member_to_field_type(typ: mypy.types.Type) -> FieldType:
    is_array = False
    if isinstance(typ, mypy.types.CallableType):
        is_array = len(typ.arg_names) > 1
        typ = typ.ret_type

    return FieldType(is_array=is_array, field_types=_instance_types_to_wtypes([typ]))


def _instance_types_to_wtypes(
    types: Sequence[mypy.types.Type],
) -> tuple[wtypes.WType | type[wtypes.WType], ...]:
    reg = pytypes.builtins_registry()

    result = list[wtypes.WType | type[wtypes.WType]]()
    for typ in types:
        assert isinstance(typ, mypy.types.Instance)
        fullname = typ.type.fullname
        pytyp = reg[fullname]
        if pytyp == pytypes.BytesBackedType:
            result.extend((wtypes.account_wtype, wtypes.biguint_wtype, wtypes.ARC4Type))
        elif pytyp == pytypes.ObjectType:
            result.append(wtypes.bytes_wtype)
        # ignoring literal types for now
        elif not isinstance(pytyp, pytypes.LiteralOnlyType):
            result.append(pytyp.wtype)
    return tuple(result)
