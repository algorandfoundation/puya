import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_TYPED_ITXN_ABI_CALL = TEST_CASES_DIR / "typed_itxn_abi_call"


def test_typed_itxn_abi_call(deployer: Deployer, asset_a: int) -> None:
    logger_client = deployer.create(_TYPED_ITXN_ABI_CALL / "logger.py").client
    logger_app_id = logger_client.app_id

    greeter_client = deployer.create(_TYPED_ITXN_ABI_CALL / "typed_c2c.py").client

    inner_fee = au.AlgoAmount.from_micro_algo(7000)

    def call(method: str, args: list[object]) -> None:
        greeter_client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args,
                static_fee=inner_fee,
            )
        )

    call("test_method_selector_kinds", [logger_app_id])
    call("test_arg_conversion", [logger_app_id])
    call("test_method_overload", [logger_app_id])
    call("test_15plus_args", [logger_app_id])
    call("test_void", [logger_app_id])
    call("test_ref_types", [logger_app_id, asset_a])
    call("test_account_to_address", [logger_app_id])
    call("test_native_tuple", [logger_app_id])
    call("test_native_tuple_method_ref", [logger_app_id])
    call("test_nested_tuples", [logger_app_id])
    call("test_native_string", [logger_app_id])
    call("test_native_bytes", [logger_app_id])
    call("test_native_uint64", [logger_app_id])
    call("test_native_biguint", [logger_app_id])
    call("test_no_args", [logger_app_id])
    call("test_is_a_b", [b"a", b"b", logger_app_id])
    call("test_named_tuples", [logger_app_id])
    call("test_arc4_struct", [logger_app_id])
    call("test_resource_encoding", [logger_app_id, asset_a])
