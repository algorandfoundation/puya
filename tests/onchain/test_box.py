import random

import algokit_utils as au
import pytest
from algokit_abi import abi

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_ALWAYS_APPROVE = b"\x06\x81\x01"  # #pragma version 6; int 1


@pytest.fixture
def box_client(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    deployer = Deployer(localnet=localnet, account=account)

    client = deployer.create(EXAMPLES_DIR / "box_storage" / "contract.py").client

    # Fund the app for box storage
    localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(10_000_000),
    )

    return client


def test_box(box_client: au.AppClient) -> None:
    box_c = b"BOX_C"
    box_refs: _BoxList = ["box_a", "b", box_c, "box_d", "box_large", *_empty_refs(3)]

    call = box_client.send.call
    response = call(_call_params("boxes_exist", box_refs=box_refs))
    assert response.abi_return == (False, False, False, False)

    call(_call_params("set_boxes", args=[56, b"Hello", "World"], box_refs=box_refs))

    response = call(_call_params("boxes_exist", box_refs=box_refs))
    assert response.abi_return == (True, True, True, True)

    call(_call_params("check_keys", box_refs=box_refs))

    response = call(_call_params("read_boxes", box_refs=box_refs))
    assert response.abi_return == (59, b"Hello", "World", 42)

    call(_call_params("indirect_extract_and_replace", box_refs=["box_large", *_empty_refs(6)]))

    call(_call_params("delete_boxes", box_refs=box_refs))

    response = call(_call_params("boxes_exist", box_refs=box_refs))
    assert response.abi_return == (False, False, False, False)

    call(_call_params("slice_box", box_refs=[b"0", box_c]))
    call(_call_params("arc4_box", box_refs=[b"d"]))

    many_ints_refs: _BoxList = ["many_ints", *_empty_refs(4)]
    fee = au.AlgoAmount.from_micro_algo(16_000)

    call(_call_params("create_many_ints", box_refs=many_ints_refs, fee=fee))

    call(_call_params("set_many_ints", args=[1, 1], box_refs=many_ints_refs, fee=fee))
    call(_call_params("set_many_ints", args=[2, 2], box_refs=many_ints_refs, fee=fee))
    call(_call_params("set_many_ints", args=[256, 256], box_refs=many_ints_refs, fee=fee))
    call(_call_params("set_many_ints", args=[511, 511], box_refs=many_ints_refs, fee=fee))
    call(_call_params("set_many_ints", args=[512, 512], box_refs=many_ints_refs, fee=fee))

    response = call(_call_params("sum_many_ints", box_refs=many_ints_refs, fee=fee))
    assert response.abi_return == (1 + 2 + 256 + 511 + 512)


def test_big_fixed_bytes_box(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["big_fixed_bytes", *_empty_refs(4)]

    call = box_client.send.call
    call(_call_params("create_big_fixed_bytes", box_refs=box_refs))
    call(_call_params("assert_big_fixed_bytes", args=[4999, b"\x00"], box_refs=box_refs))
    call(_call_params("update_big_fixed_bytes", args=[4990, b"\x0f" * 10], box_refs=box_refs))
    call(_call_params("assert_big_fixed_bytes", args=[4999, b"\x0f"], box_refs=box_refs))

    response = call(_call_params("slice_big_fixed_bytes", args=[4990, 5000], box_refs=box_refs))
    assert response.abi_return == b"\x0f" * 10


def test_big_bytes_box(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["big_bytes", *_empty_refs(4)]

    call = box_client.send.call
    call(_call_params("create_big_bytes", args=[6000], box_refs=box_refs))
    call(_call_params("assert_big_bytes", args=[5999, b"\x00"], box_refs=box_refs))
    call(_call_params("update_big_bytes", args=[5990, b"\x0f" * 10], box_refs=box_refs))
    call(_call_params("assert_big_bytes", args=[5999, b"\x0f"], box_refs=box_refs))

    response = call(_call_params("slice_big_bytes", args=[5990, 6000], box_refs=box_refs))
    assert response.abi_return == b"\x0f" * 10


def test_dynamic_box(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["dynamic_box", *_empty_refs(7)]

    call = box_client.send.call
    call(_call_params("create_dynamic_box", box_refs=box_refs))

    response = call(_call_params("append_dynamic_box", args=[0], box_refs=box_refs))
    assert response.abi_return == 0, "expected empty array"

    response = call(_call_params("sum_dynamic_box", box_refs=box_refs))
    assert response.abi_return == 0, "expected sum to be 0"

    response = call(_call_params("append_dynamic_box", args=[5], box_refs=box_refs))
    assert response.abi_return == 5, "expected 5 items"

    response = call(_call_params("sum_dynamic_box", box_refs=box_refs))
    expected_sum = sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("append_dynamic_box", args=[5], box_refs=box_refs))
    assert response.abi_return == 10, "expected 10 items"

    response = call(_call_params("sum_dynamic_box", box_refs=box_refs))
    expected_sum = 2 * sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("pop_dynamic_box", args=[5], box_refs=box_refs))
    assert response.abi_return == 5, "expected 5 items"

    response = call(_call_params("sum_dynamic_box", box_refs=box_refs))
    expected_sum = sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    # append until exceeding max stack array size
    for i in range(110):
        response = call(_call_params("append_dynamic_box", args=[5], box_refs=box_refs))
        expected_items = 5 * (i + 2)
        assert response.abi_return == expected_items, f"expected {expected_items} items"

    # use simulate to ignore large op budget requirements
    abi_return = _simulate_call(box_client, "sum_dynamic_box", box_refs=box_refs)
    expected_sum = 111 * sum(range(5))
    assert abi_return == expected_sum, f"expected sum to be {expected_sum}"

    # compare actual box contents too
    expected_array = list(range(5)) * 111
    dynamic_box_bytes = box_client.get_box_value(b"dynamic_box")
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    dynamic_box = abi.ABIType.from_string("uint64[]").decode(dynamic_box_bytes)
    assert dynamic_box == expected_array, "expected box contents to be correct"

    call(_call_params("write_dynamic_box", args=[0, 100], box_refs=box_refs))
    abi_return = _simulate_call(box_client, "sum_dynamic_box", box_refs=box_refs)
    expected_sum = 111 * sum(range(5)) + 100
    assert abi_return == expected_sum, f"expected sum to be {expected_sum}"

    call(_call_params("delete_dynamic_box", box_refs=box_refs))


def test_nested_struct_box(box_client: au.AppClient, account: au.AddressWithSigners) -> None:
    box_refs: _BoxList = ["box", *_empty_refs(7)]
    fee = au.AlgoAmount.from_micro_algo(2_000)

    r = iter(range(1, 256))

    def n() -> int:
        return next(r)

    def inner_struct() -> dict[str, object]:
        c, arr, d = (n() for _ in range(3))
        return {"c": c, "arr_arr": [[arr] * 4 for _ in range(3)], "d": d}

    struct = {
        "a": n(),
        "inner": inner_struct(),
        # arc-56 cannot represent an arrays of structs currently,
        # so convert struct to a tuple
        "woah": [tuple(inner_struct().values()) for _ in range(3)],
        "b": n(),
    }
    assert n() < 100, "too many ints"

    composer = box_client.algorand.new_group()
    # add op up
    composer.add_app_create(
        au.AppCreateParams(
            approval_program=_ALWAYS_APPROVE,
            clear_state_program=_ALWAYS_APPROVE,
            on_complete=au.OnApplicationComplete.DeleteApplication,
            sender=account.addr,
            note=random.randbytes(8),
        )
    )
    composer.add_app_call_method_call(
        box_client.params.call(_call_params("set_nested_struct", args=[struct], box_refs=box_refs))
    )
    composer.send()

    call = box_client.send.call
    response = call(_call_params("nested_read", args=[1, 2, 3], box_refs=box_refs, fee=fee))
    assert response.abi_return == 33, "expected sum to be correct"

    call(_call_params("nested_write", args=[1, 10], box_refs=box_refs, fee=fee))
    response = call(_call_params("nested_read", args=[1, 2, 3], box_refs=box_refs, fee=fee))
    assert response.abi_return == 60, "expected sum to be correct"

    # modify local struct to match expected modifications performed by nested_write
    struct["a"] = 10
    struct["b"] = 11
    inner = struct["inner"]
    assert isinstance(inner, dict)
    inner["arr_arr"][1][1] = 12
    inner["c"] = 13
    inner["d"] = 14
    woah = struct["woah"]
    assert isinstance(woah, list)
    woah_1 = list(woah[1])  # convert tuple to list for mutation
    woah_1[1][1][1] = 15  # woah[1].arr_arr[1][1]
    woah[1] = tuple(woah_1)

    # LargeNestedStruct does not appear in spec
    large_nested_struct_type = abi.StructType(
        struct_name="LargeNestedStruct",
        fields={
            "padding": abi.ABIType.from_string("byte[4096]"),
            "nested": box_client.app_spec.structs["NestedStruct"],
        },
    )
    box_contents = box_client.get_box_value_from_abi_type(b"box", large_nested_struct_type)
    assert box_contents == {
        "padding": bytes(4096),
        "nested": struct,
    }, "expected box contents to be correct"


def test_dynamic_arr_in_struct_box(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["dynamic_arr_struct", *_empty_refs(7)]

    call = box_client.send.call
    call(_call_params("create_dynamic_arr_struct", box_refs=box_refs))

    response = call(_call_params("append_dynamic_arr_struct", args=[0], box_refs=box_refs))
    assert response.abi_return == 0, "expected empty array"

    response = call(_call_params("sum_dynamic_arr_struct", box_refs=box_refs))
    expected_sum = 3
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("append_dynamic_arr_struct", args=[5], box_refs=box_refs))
    assert response.abi_return == 5, "expected 5 items"

    response = call(_call_params("sum_dynamic_arr_struct", box_refs=box_refs))
    expected_sum = 3 + 1 * sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("append_dynamic_arr_struct", args=[5], box_refs=box_refs))
    assert response.abi_return == 10, "expected 10 items"

    response = call(_call_params("sum_dynamic_arr_struct", box_refs=box_refs))
    expected_sum = 3 + 2 * sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("pop_dynamic_arr_struct", args=[5], box_refs=box_refs))
    assert response.abi_return == 5, "expected 5 items"

    response = call(_call_params("sum_dynamic_arr_struct", box_refs=box_refs))
    expected_sum = 3 + 1 * sum(range(5))
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    response = call(_call_params("pop_dynamic_arr_struct", args=[5], box_refs=box_refs))
    assert response.abi_return == 0, "expected 0 items"

    response = call(_call_params("sum_dynamic_arr_struct", box_refs=box_refs))
    expected_sum = 3
    assert response.abi_return == expected_sum, f"expected sum to be {expected_sum}"

    # append until exceeding max stack array size
    num_appends = 111
    for i in range(num_appends):
        response = call(_call_params("append_dynamic_arr_struct", args=[5], box_refs=box_refs))
        expected_items = 5 * (i + 1)
        assert response.abi_return == expected_items, f"expected {expected_items} items"

    # use simulate to ignore large op budget requirements
    abi_return = _simulate_call(box_client, "sum_dynamic_arr_struct", box_refs=box_refs)
    expected_sum = 3 + num_appends * sum(range(5))
    assert abi_return == expected_sum, f"expected sum to be {expected_sum}"

    # compare actual box contents too
    expected_array = list(range(5)) * num_appends
    dynamic_box_bytes = box_client.get_box_value(b"dynamic_arr_struct")
    assert len(dynamic_box_bytes) > 4096, "expected box contents to exceed max stack value size"
    dynamic_box = abi.ABIType.from_string("(uint64,uint64[],uint64,uint64[])").decode(
        dynamic_box_bytes
    )
    assert dynamic_box == (1, expected_array, 2, []), "expected box contents to be correct"

    call(_call_params("write_dynamic_arr_struct", args=[0, 100], box_refs=box_refs))
    abi_return = _simulate_call(box_client, "sum_dynamic_arr_struct", box_refs=box_refs)
    expected_sum = 3 + num_appends * sum(range(5)) + 100
    assert abi_return == expected_sum, f"expected sum to be {expected_sum}"

    call(_call_params("delete_dynamic_arr_struct", box_refs=box_refs))


def test_too_many_bools(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["too_many_bools", *_empty_refs(7)]

    call = box_client.send.call
    call(_call_params("create_bools", box_refs=box_refs))

    call(_call_params("set_bool", args=[0, True], box_refs=box_refs))
    call(_call_params("set_bool", args=[42, True], box_refs=box_refs))
    call(_call_params("set_bool", args=[500, True], box_refs=box_refs))
    call(_call_params("set_bool", args=[32_999, True], box_refs=box_refs))

    abi_return = _simulate_call(box_client, "sum_bools", args=[3], box_refs=box_refs)
    expected_sum = 3
    assert abi_return == expected_sum, f"expected sum to be {expected_sum}"

    too_many_bools_actual = box_client.get_box_value_from_abi_type(
        b"too_many_bools", abi.ABIType.from_string("bool[33000]")
    )
    too_many_bools_expected = [False] * 33_000
    too_many_bools_expected[0] = True
    too_many_bools_expected[42] = True
    too_many_bools_expected[500] = True
    too_many_bools_expected[32_999] = True

    assert too_many_bools_actual == too_many_bools_expected, "expected box contents to be correct"


def test_box_ref(box_client: au.AppClient) -> None:
    box_refs: _BoxList = ["box_ref", b"blob", *_empty_refs(6)]
    box_client.send.call(_call_params("test_box_ref", box_refs=box_refs))


def test_box_map(box_client: au.AppClient) -> None:
    call = box_client.send.call

    call(_call_params("box_map_test", box_refs=[_int_key(0), _int_key(1)]))

    key = 2
    box_refs: _BoxList = [_int_key(key)]
    response = call(_call_params("box_map_exists", args=[key], box_refs=box_refs))
    assert not response.abi_return, "Box does not exist (yet)"

    call(_call_params("box_map_set", args=[key, "Hello 123"], box_refs=box_refs))

    response = call(_call_params("box_map_get", args=[key], box_refs=box_refs))
    assert response.abi_return == "Hello 123", "Box value is what was set"

    response = call(_call_params("box_map_exists", args=[key], box_refs=box_refs))
    assert response.abi_return, "Box exists"

    call(_call_params("box_map_del", args=[key], box_refs=box_refs))

    response = call(_call_params("box_map_exists", args=[key], box_refs=box_refs))
    assert not response.abi_return, "Box does not exist after deletion"


_BoxList = list[au.BoxReference | au.BoxIdentifier]


def _int_key(key: int) -> bytes:
    return key.to_bytes(8)


def _empty_refs(num: int) -> _BoxList:
    return [au.BoxReference(0, b"")] * num


def _call_params(
    method: str,
    *,
    args: list[object] | None = None,
    box_refs: _BoxList | None = None,
    fee: au.AlgoAmount | None = None,
) -> au.AppClientMethodCallParams:
    return au.AppClientMethodCallParams(
        method=method,
        args=args or [],
        box_references=box_refs,
        static_fee=fee,
        note=random.randbytes(8),
    )


def _simulate_call(
    client: au.AppClient,
    method: str,
    *,
    args: list[object] | None = None,
    box_refs: _BoxList | None = None,
) -> au.ABIValue:
    result = (
        client.algorand.new_group()
        .add_app_call_method_call(
            client.params.call(_call_params(method, args=args, box_refs=box_refs))
        )
        .simulate(extra_opcode_budget=20_000)
    )
    return result.returns[0].value
