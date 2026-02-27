import random
from pathlib import Path

import algokit_utils as au
import pytest
from algokit_algod_client import models as algod
from algokit_common import public_key_from_address

from tests import TEST_CASES_DIR
from tests.utils import arc4_encode, get_state_delta_as_dict
from tests.utils.deployer import Deployer

_ARRAY_DIR = TEST_CASES_DIR / "array"


def test_array_uint64(deployer_o: Deployer) -> None:
    client = deployer_o.create(_ARRAY_DIR / "uint64.py").client

    _simulate(client, "test_array")
    _simulate(client, "test_array_extend")
    _simulate(client, "test_array_multiple_append")
    _simulate(client, "test_iteration")
    _simulate(client, "test_array_copy_and_extend")
    _simulate(client, "test_array_evaluation_order")

    _simulate(client, "test_array_assignment_maximum_cursage")

    _simulate(client, "test_allocations", args=[255])
    with pytest.raises(au.LogicError, match="no available slots\t\t<-- Error"):
        _simulate(client, "test_allocations", args=[256])

    with pytest.raises(au.LogicError, match="max array length exceeded\t\t<-- Error"):
        _simulate(client, "test_array_too_long")

    _simulate(client, "test_quicksort")
    _simulate(client, "test_unobserved_write")


def test_array_static_size(deployer_o: Deployer) -> None:
    client = deployer_o.create(_ARRAY_DIR / "static_size.py").client

    # Fund app for box storage
    deployer_o.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer_o.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    x1, y1 = 3, 4
    x2, y2 = 6, 8
    sender = public_key_from_address(deployer_o.account.addr)

    response = _simulate(client, "test_array", args=[x1, y1, x2, y2])
    assert response.returns[0].value == 15
    assert _get_box_state_from_trace(response, b"a") == arc4_encode(
        "(uint64,uint64,(uint64,uint64,address,(uint64,uint64),uint512))[]",
        [
            (0, 0, (5, 1, sender, (2, 1), 1)),
            (x1, y1, (5, 2, sender, (3, 4), 2)),
            (x2, y2, (5, 3, sender, (4, 9), 3)),
        ],
    )

    response = _simulate(client, "test_arc4_conversion", args=[5])
    assert response.returns[0].value == [1, 2, 3, 4, 5]

    response = _simulate(client, "sum_array", args=[[1, 2, 3, 4, 5]])
    assert response.returns[0].value == 15

    response = _simulate(client, "test_bool_array", args=[5])
    assert response.returns[0].value == 2
    response = _simulate(client, "test_bool_array", args=[4])
    assert response.returns[0].value == 2
    response = _simulate(client, "test_bool_array", args=[6])
    assert response.returns[0].value == 3
    response = _simulate(client, "test_bool_array", args=[5])
    assert response.returns[0].value == 2

    response = _simulate(client, "test_extend_from_tuple", args=[[[1, 2], [3, 4]]])
    assert response.returns[0].value == [(1, 2), (3, 4)]

    response = _simulate(client, "test_extend_from_arc4_tuple", args=[[[1, 2], [3, 4]]])
    assert response.returns[0].value == [(1, 2), (3, 4)]

    response = _simulate(client, "test_arc4_bool")
    assert response.returns[0].value == [False, True]


def test_immutable_array_init(immutable_array_init_client: au.AppClient) -> None:
    client = immutable_array_init_client
    _simulate(client, "test_immutable_array_init")
    _simulate(client, "test_immutable_array_init_without_type_generic")
    _simulate(client, "test_reference_array_init")
    _simulate(client, "test_immutable_array_init_without_type_generic")


def test_immutable_array(immutable_array_client: au.AppClient) -> None:
    client = immutable_array_client

    response = _simulate(client, "test_uint64_array")
    global_state = _get_global_state_delta(response)
    assert global_state[b"a"] == arc4_encode("uint64[]", [42, 0, 23, 2, *range(10), 44])

    response = _simulate(client, "test_biguint_array")
    box_value = _get_box_state_from_trace(response, b"biguint")
    assert box_value == arc4_encode("uint512[]", [0, *range(5), 2**512 - 2, 2**512 - 1])

    response = _simulate(client, "test_fixed_size_tuple_array")
    global_state = _get_global_state_delta(response)
    assert global_state[b"c"] == arc4_encode(
        "(uint64,uint64)[]", [(i + 1, i + 2) for i in range(4)]
    )

    response = _simulate(client, "test_fixed_size_named_tuple_array")
    global_state = _get_global_state_delta(response)
    assert global_state[b"d"] == arc4_encode(
        "(uint64,bool,bool)[]", [(i, i % 2 == 0, i * 3 % 2 == 0) for i in range(5)]
    )

    response = _simulate(client, "test_dynamic_sized_tuple_array")
    global_state = _get_global_state_delta(response)
    assert global_state[b"e"] == arc4_encode(
        "(uint64,byte[])[]", [(i + 1, b"\x00" * i) for i in range(4)]
    )

    response = _simulate(client, "test_dynamic_sized_named_tuple_array")
    global_state = _get_global_state_delta(response)
    assert global_state[b"f"] == arc4_encode(
        "(uint64,string)[]", [(i + 1, " " * i) for i in range(4)]
    )

    response = _simulate(client, "test_bit_packed_tuples")
    global_state = _get_global_state_delta(response)
    assert global_state[b"bool2"] == arc4_encode(
        "(bool,bool)[]", [(i == 0, i == 1) for i in range(5)]
    )
    assert global_state[b"bool7"] == arc4_encode(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [(i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i + 1) for i in range(5)],
    )
    assert global_state[b"bool8"] == arc4_encode(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [
            (i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i == 7, i + 1)
            for i in range(5)
        ],
    )
    assert global_state[b"bool9"] == arc4_encode(
        "(uint64,bool,bool,bool,bool,bool,bool,bool,bool,bool,uint64)[]",
        [
            (i, i == 0, i == 1, i == 2, i == 3, i == 4, i == 5, i == 6, i == 7, i == 8, i + 1)
            for i in range(5)
        ],
    )

    append = 5
    arr = [(i, i % 2 == 0, i % 3 == 0) for i in range(append)]
    response = _simulate(client, "test_convert_to_array_and_back", args=[arr, append])
    assert response.returns[0].value == [*arr, *arr]

    for tuple_type in ("arc4", "native"):
        response = _simulate(client, f"test_concat_with_{tuple_type}_tuple", args=[(3, 4)])
        assert response.returns[0].value == [1, 2, 3, 4]

    for tuple_type in ("native", "arc4"):
        method = f"test_dynamic_concat_with_{tuple_type}_tuple"
        response = _simulate(client, method, args=[("c", "d")])
        assert response.returns[0].value == ["a", "b", "c", "d"]

    response = _simulate(
        client,
        "test_concat_immutable_dynamic",
        args=[[[1, "one"], [2, "foo"]], [[3, "tree"], [4, "floor"]]],
    )
    assert response.returns[0].value == [
        (1, "one"),
        (2, "foo"),
        (3, "tree"),
        (4, "floor"),
    ]

    response = _simulate(client, "test_immutable_arc4", args=[[[1, 2], [3, 4], [5, 6]]])
    assert response.returns[0].value == [
        (1, 2),
        (3, 4),
        (1, 2),
    ]

    response = _simulate(client, "test_imm_fixed_arr")
    expected_imm_fixed_arr_value = [
        (2, 3),
        (2, 3),
        (2, 3),
    ]
    assert response.returns[0].value == expected_imm_fixed_arr_value
    global_state = _get_global_state_delta(response)
    assert global_state[b"imm_fixed_arr"] == arc4_encode(
        "(uint64,uint64)[3]",
        expected_imm_fixed_arr_value,
    )


_EXPECTED_LENGTH_20 = [False, False, True, *[False] * 17]


@pytest.mark.parametrize("length", [0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17])
def test_immutable_bool_array(immutable_array_client: au.AppClient, length: int) -> None:
    client = immutable_array_client
    response = _simulate(client, "test_bool_array", args=[length])
    expected = _EXPECTED_LENGTH_20[:length]
    global_state = _get_global_state_delta(response)
    assert global_state[b"g"] == arc4_encode("bool[]", expected)


def test_immutable_routing(immutable_array_client: au.AppClient) -> None:
    client = immutable_array_client

    response = _simulate(
        client,
        "sum_uints_and_lengths_and_trues",
        args=[
            list(range(5)),
            [i % 2 == 0 for i in range(6)],
            [(i, i % 2 == 0, i % 3 == 0) for i in range(7)],
            [(i, " " * i) for i in range(8)],
        ],
    )
    assert response.returns[0].value == (10, 3, 21 + 4 + 3, 28 * 2)

    append = 4
    response = _simulate(client, "test_uint64_return", args=[append])
    assert response.returns[0].value == [1, 2, 3, *range(append)]

    append = 5
    response = _simulate(client, "test_bool_return", args=[append])
    assert response.returns[0].value == [
        *[True, False, True, False, True],
        *(i % 2 == 0 for i in range(append)),
    ]

    append = 6
    response = _simulate(client, "test_tuple_return", args=[append])
    assert response.returns[0].value == [
        (0, True, False),
        *((i, i % 2 == 0, i % 3 == 0) for i in range(append)),
    ]

    append = 3
    response = _simulate(client, "test_dynamic_tuple_return", args=[append])
    assert response.returns[0].value == [
        (0, "Hello"),
        *((i, " " * i) for i in range(append)),
    ]


def test_nested_immutable(immutable_array_client: au.AppClient) -> None:
    client = immutable_array_client

    response = _simulate(
        client,
        "test_nested_array",
        args=[5, [[i * j for i in range(5)] for j in range(3)]],
    )
    assert response.returns[0].value == [
        0,
        10,
        20,
        0,
        0,
        1,
        3,
        6,
    ]


@pytest.fixture(scope="module")
def immutable_array_init_client(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    return _create_client(_ARRAY_DIR / "immutable_init.py", localnet_clients, account)


@pytest.fixture(scope="module")
def immutable_array_client(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    return _create_client(_ARRAY_DIR / "immutable.py", localnet_clients, account)


def _create_client(
    path: Path, localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    deployer = Deployer(localnet=localnet, account=account)
    result = deployer.create(path)
    localnet.account.ensure_funded(
        account_to_fund=result.client.app_address,
        dispenser_account=account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(400_000),
    )
    return result.client


def _simulate(
    client: au.AppClient,
    method: str,
    *,
    args: list[object] | None = None,
) -> au.SendTransactionComposerResults:
    return (
        client.algorand.new_group()
        .add_app_call_method_call(
            client.params.call(
                au.AppClientMethodCallParams(
                    method=method,
                    args=args or [],
                    note=random.randbytes(8),
                )
            )
        )
        .simulate(
            extra_opcode_budget=20_000,
            allow_unnamed_resources=True,
            exec_trace_config=algod.SimulateTraceConfig(
                enable=True,
                state_change=True,
            ),
        )
    )


def _get_global_state_delta(
    response: au.SendTransactionComposerResults,
) -> dict[bytes, bytes | int | None]:
    return get_state_delta_as_dict(response.confirmations[0].global_state_delta)


def _get_box_state_from_trace(response: au.SendTransactionComposerResults, key: bytes) -> bytes:
    assert response.simulate_response is not None
    sim = response.simulate_response.txn_groups[0]
    trace = sim.txn_results[0].exec_trace
    assert trace is not None
    assert trace.approval_program_trace is not None
    scs = [sc for t in trace.approval_program_trace for sc in (t.state_changes or [])]

    matching = [
        sc
        for sc in scs
        if sc.app_state_type == "b"  # box
        and sc.operation == "w"  # write
        and sc.key == key
    ]
    if not matching:
        raise ValueError(f"No box state change found for key {key!r}")
    sc = matching[-1]  # get last matching write
    assert sc.new_value is not None
    assert sc.new_value.bytes_ is not None
    return sc.new_value.bytes_  # already bytes, no need to decode
