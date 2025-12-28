import algokit_utils as au
from algokit_abi import abi

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer


def test_dynamic_arrays_static_element(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client

    static_struct_t = abi.ABIType.from_string("(uint64,byte[2])")
    static_arr_t = abi.DynamicArrayType(static_struct_t)
    static_struct0 = (3, bytes((4, 5)))
    static_struct1 = (2**42, bytes((42, 255)))

    static_result = app_client.send.call(
        au.AppClientMethodCallParams(method="test_static_elements")
    )
    (static_arr_bytes, static_0_bytes, static_1_bytes) = decode_logs(
        static_result.confirmation.logs, "bbb"
    )

    assert static_arr_bytes == static_arr_t.encode([static_struct0, static_struct1])
    assert static_0_bytes == static_struct_t.encode(static_struct0)
    assert static_1_bytes == static_struct_t.encode(static_struct1)


def test_dynamic_arrays_dynamic_element(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client

    dynamic_struct_t = abi.ABIType.from_string("(string,string)")
    dynamic_arr_t = abi.ABIType.from_string("(string,string)[]")
    dynamic_struct0 = ("a", "bee")
    dynamic_struct1 = ("Hello World", "a")

    dynamic_result = app_client.send.call(
        au.AppClientMethodCallParams(method="test_dynamic_elements")
    )
    (
        dynamic_arr_bytes,
        dynamic_0_bytes,
        dynamic_1_bytes,
        dynamic_2_bytes,
        dynamic_arr_bytes_01,
        dynamic_arr_bytes_0,
        empty_arr,
    ) = decode_logs(dynamic_result.confirmation.logs, "b" * 7)

    assert dynamic_arr_bytes == dynamic_arr_t.encode(
        [dynamic_struct0, dynamic_struct1, dynamic_struct0]
    )
    assert dynamic_0_bytes == dynamic_struct_t.encode(dynamic_struct0)
    assert dynamic_1_bytes == dynamic_struct_t.encode(dynamic_struct1)
    assert dynamic_2_bytes == dynamic_struct_t.encode(dynamic_struct0)
    assert dynamic_arr_bytes_01 == dynamic_arr_t.encode([dynamic_struct0, dynamic_struct1])
    assert dynamic_arr_bytes_0 == dynamic_arr_t.encode([dynamic_struct0])
    assert empty_arr == dynamic_arr_t.encode([])


def test_dynamic_arrays_mixed_single_dynamic(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client

    mixed1_struct_t = abi.ABIType.from_string("(uint64,string,uint64)")
    mixed1_arr_t = abi.DynamicArrayType(mixed1_struct_t)
    mixed1_struct0 = (3, "a", 2**42)
    mixed1_struct1 = (2**42, "bee", 3)

    mixed_single_result = app_client.send.call(
        au.AppClientMethodCallParams(method="test_mixed_single_dynamic_elements")
    )
    (mixed1_arr_bytes, mixed1_0_bytes, mixed1_1_bytes) = decode_logs(
        mixed_single_result.confirmation.logs, "bbb"
    )

    assert mixed1_arr_bytes == mixed1_arr_t.encode([mixed1_struct0, mixed1_struct1])
    assert mixed1_0_bytes == mixed1_struct_t.encode(mixed1_struct0)
    assert mixed1_1_bytes == mixed1_struct_t.encode(mixed1_struct1)


def test_dynamic_arrays_mixed_multiple_dynamic(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client

    mixed2_struct_t = abi.ABIType.from_string("(uint64,string,uint64,uint16[],uint64)")
    mixed2_arr_t = abi.DynamicArrayType(mixed2_struct_t)
    mixed2_struct0 = (3, "a", 2**42, (2**16 - 1, 0, 42), 3)
    mixed2_struct1 = (2**42, "bee", 3, (1, 2, 3, 4), 2**42)

    mixed_multiple_result = app_client.send.call(
        au.AppClientMethodCallParams(method="test_mixed_multiple_dynamic_elements")
    )
    (mixed2_arr_bytes, mixed2_0_bytes, mixed2_1_bytes) = decode_logs(
        mixed_multiple_result.confirmation.logs, "bbb"
    )

    assert mixed2_arr_bytes == mixed2_arr_t.encode([mixed2_struct0, mixed2_struct1])
    assert mixed2_0_bytes == mixed2_struct_t.encode(mixed2_struct0)
    assert mixed2_1_bytes == mixed2_struct_t.encode(mixed2_struct1)


def test_nested_struct(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client
    app_client.send.call(au.AppClientMethodCallParams(method="test_nested_struct_replacement"))


def test_nested_tuple(
    deployer: Deployer,
) -> None:
    app_client = deployer.create(TEST_CASES_DIR / "arc4_dynamic_arrays").client
    app_client.send.call(au.AppClientMethodCallParams(method="test_nested_tuple_modification"))
