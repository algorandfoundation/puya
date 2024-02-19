from collections.abc import Iterable

import mypy.nodes
from puya.awst.nodes import TxnFields
from puya.awst_build import constants

from tests import EXAMPLES_DIR
from tests.utils import get_awst_cache


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
    all_fields = {f.python_name for f in TxnFields.all_fields()}
    gtxn_types = [t.gtxn for t in constants.TRANSACTION_TYPE_TO_CLS.values()]
    gtxn_types.append(constants.CLS_TRANSACTION_BASE)
    for type_info in _get_type_infos(gtxn_types):
        unknown = sorted(set(type_info.protocol_members) - all_fields)
        assert not unknown, f"{type_info.fullname}: Unknown TxnField members: {unknown}"


def test_inner_transaction_field_setters() -> None:
    param_fields = {f.python_name for f in TxnFields.inner_transaction_param_fields()}
    for type_info in _get_type_infos(
        t.itxn_fields for t in constants.TRANSACTION_TYPE_TO_CLS.values()
    ):
        init_args: set[str] | None = None
        for member in ("__init__", "set"):
            func_def = type_info.names[member].node
            assert isinstance(func_def, mypy.nodes.FuncDef)
            arg_names = [a for a in func_def.arg_names if a is not None]
            arg_names.remove("self")
            unknown = sorted(set(arg_names) - param_fields)
            assert not unknown, f"{type_info.fullname}: Unknown TxnField param members: {unknown}"

            if init_args is None:
                init_args = set(arg_names)
            else:
                difference = init_args.symmetric_difference(set(arg_names))
                assert (
                    not difference
                ), f"{type_info.fullname}.{member} field difference: {difference}"


def test_inner_transaction_members() -> None:
    all_fields = {f.python_name for f in TxnFields.all_fields()}
    for type_info in _get_type_infos(
        t.itxn_result for t in constants.TRANSACTION_TYPE_TO_CLS.values()
    ):
        unknown = sorted(set(type_info.protocol_members) - all_fields)
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
    missing_fields = [
        f.python_name for f in TxnFields.all_fields() if f.python_name not in seen_fields
    ]
    assert not missing_fields, f"Txn Fields not mapped: {missing_fields}"
