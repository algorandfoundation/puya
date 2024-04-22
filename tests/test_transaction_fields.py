import json
from collections.abc import Iterable

import mypy.nodes
from puya.awst.nodes import INNER_PARAM_TXN_FIELDS, TXN_FIELDS
from puya.awst_build import constants
from puya.awst_build.eb.transaction import get_field_python_name

from tests import EXAMPLES_DIR, VCS_ROOT
from tests.utils import get_awst_cache

_ALL_PYTHON_TXN_FIELD_NAMES = set(map(get_field_python_name, TXN_FIELDS))
_INNER_TRANSACTION_PYTHON_TXN_FIELD_NAMES = set(map(get_field_python_name, INNER_PARAM_TXN_FIELDS))
_INTENTIONALLY_OMITTED_INNER_TXN_FIELDS = {
    # the need to use approval / clear_state pages is abstracted away by
    # allowing a tuple of pages in the stubs layer
    "approval_program_pages",
    "clear_state_program_pages",
    # only allow enum version of type
    "type_bytes",
}


def _get_type_infos(type_names: Iterable[str]) -> Iterable[mypy.nodes.TypeInfo]:
    awst_cache = get_awst_cache(EXAMPLES_DIR)

    for type_name in type_names:
        module_id, symbol_name = type_name.rsplit(".", maxsplit=1)
        module = awst_cache.context.parse_result.manager.modules[module_id]

        symbol = module.names[symbol_name]
        node = symbol.node
        assert isinstance(node, mypy.nodes.TypeInfo), f"{type_name} not found in {module}"
        yield node


def test_group_transaction_members() -> None:
    gtxn_types = [t.gtxn for t in constants.TRANSACTION_TYPE_TO_CLS.values()]
    gtxn_types.append(constants.CLS_TRANSACTION_BASE)
    for type_info in _get_type_infos(gtxn_types):
        unknown = sorted(set(type_info.protocol_members) - _ALL_PYTHON_TXN_FIELD_NAMES)
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


def test_inner_transaction_field_setters() -> None:
    unmapped = _INNER_TRANSACTION_PYTHON_TXN_FIELD_NAMES - _INTENTIONALLY_OMITTED_INNER_TXN_FIELDS
    for type_info in _get_type_infos(
        t.itxn_fields for t in constants.TRANSACTION_TYPE_TO_CLS.values()
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
    for type_info in _get_type_infos(
        t.itxn_result for t in constants.TRANSACTION_TYPE_TO_CLS.values()
    ):
        unknown = sorted(set(type_info.protocol_members) - _ALL_PYTHON_TXN_FIELD_NAMES)
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


def test_txn_fields() -> None:
    # collect all fields that are protocol members
    txn_types = [t.gtxn for t in constants.TRANSACTION_TYPE_TO_CLS.values()]
    txn_types.append(constants.CLS_TRANSACTION_BASE)
    txn_types.extend(t.itxn_result for t in constants.TRANSACTION_TYPE_TO_CLS.values())
    seen_fields = set[str]()
    for type_info in _get_type_infos(txn_types):
        for member in type_info.protocol_members:
            seen_fields.add(member)

    # add fields that are arguments
    for type_info in _get_type_infos(
        t.itxn_fields for t in constants.TRANSACTION_TYPE_TO_CLS.values()
    ):
        for member in ("__init__", "set"):
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            seen_fields.update(
                arg for arg in func_def.arg_names if arg is not None and arg != "self"
            )

    # anything missing is an error
    missing_fields = sorted(_ALL_PYTHON_TXN_FIELD_NAMES - seen_fields)
    assert not missing_fields, f"Txn Fields not mapped: {missing_fields}"


def test_mismatched_langspec_txn_fields() -> None:
    langspec_path = VCS_ROOT / "langspec.puya.json"
    langspec = json.loads(langspec_path.read_text())
    arg_enums = langspec["arg_enums"]
    all_txn_fields = {field["name"] for field in arg_enums["txn"]}
    txn_array_fields = {field["name"] for field in arg_enums["txna"]}
    txn_single_fields = all_txn_fields - txn_array_fields
    inner_txn_fields = {field["name"] for field in arg_enums["itxn_field"]}

    assert not _set_difference(
        all_txn_fields, [f.immediate for f in TXN_FIELDS]
    ), "txn field mismatch"

    assert not _set_difference(
        txn_single_fields, [f.immediate for f in TXN_FIELDS if not f.is_array]
    ), "single txn field mismatch"

    assert not _set_difference(
        txn_array_fields, [f.immediate for f in TXN_FIELDS if f.is_array]
    ), "array txn field mismatch"

    assert not _set_difference(
        inner_txn_fields, [f.immediate for f in TXN_FIELDS if f.is_inner_param]
    ), "inner txn field mismatch"


def _set_difference(expected: set[str], actual: list[str]) -> list[str]:
    return list(expected.symmetric_difference(actual))
