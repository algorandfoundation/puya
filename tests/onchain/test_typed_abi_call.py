import random

import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_TYPED_ABI_CALL_DIR = TEST_CASES_DIR / "typed_abi_call"


def test_typed_abi_call(deployer: Deployer, asset_a: int) -> None:
    # Create logger app
    logger_client = deployer.create(_TYPED_ABI_CALL_DIR / "logger.py").client

    # Create typed_c2c app
    client = deployer.create(_TYPED_ABI_CALL_DIR / "typed_c2c.py").client

    def call(
        method: str,
        args: list[object] | None = None,
    ) -> None:
        client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args or [logger_client.app_id],
                static_fee=au.AlgoAmount.from_micro_algo(7000),
                app_references=[logger_client.app_id],
                note=random.randbytes(8),
            )
        )

    call("test_method_selector_kinds")
    call("test_arg_conversion")
    call("test_method_overload")
    call("test_15plus_args")
    call("test_void")
    call("test_ref_types", args=[logger_client.app_id, asset_a])
    call("test_account_to_address")
    call("test_native_tuple")
    call("test_native_tuple_method_ref")
    call("test_nested_tuples")
    call("test_native_string")
    call("test_native_bytes")
    call("test_native_uint64")
    call("test_native_biguint")
    call("test_no_args")
    call("test_is_a_b", args=[b"a", b"b", logger_client.app_id])
    call("test_named_tuples")
    call("test_arc4_struct")
    call("test_resource_encoding", args=[logger_client.app_id, asset_a])
