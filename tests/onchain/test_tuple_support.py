import algokit_utils as au
from algokit_abi import abi

from tests import TEST_CASES_DIR
from tests.utils import decode_logs
from tests.utils.deployer import Deployer

_TUPLE_SUPPORT_DIR = TEST_CASES_DIR / "tuple_support"


def test_tuple_support(deployer: Deployer) -> None:
    response = deployer.create_bare(_TUPLE_SUPPORT_DIR / "tuple_support.py")

    assert decode_logs(response.logs, "iuiiiuuuuu") == [
        306,
        "Hello, world!",
        0,
        2,
        1,
        "nanananana",
        "non_empty_tuple called",
        "not empty",
        "get_uint_with_side_effect called",
        "not empty2",
    ]


def test_tuple_comparisons(deployer: Deployer) -> None:
    response = deployer.create_bare(_TUPLE_SUPPORT_DIR / "tuple_comparisons.py")
    expected_log_values = list(range(42, 48))

    assert (
        decode_logs(response.confirmation.logs, "i" * len(expected_log_values))
        == expected_log_values
    )


def test_nested_tuples(deployer: Deployer) -> None:
    client = deployer.create(_TUPLE_SUPPORT_DIR / "nested_tuples.py").client

    # Fund the app
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    call = client.send.call

    call(au.AppClientMethodCallParams(method="run_tests"))

    response = call(
        au.AppClientMethodCallParams(
            method="nested_tuple_params",
            args=[("Hello", (b"World", (123,)))],
        )
    )
    assert response.abi_return == (b"World", ("Hello", 123))

    response = call(
        au.AppClientMethodCallParams(
            method="named_tuple",
            args=[(1, b"2", "3")],
        )
    )
    assert response.abi_return == {"a": 1, "b": b"2", "c": "3"}

    response = call(
        au.AppClientMethodCallParams(
            method="nested_named_tuple_params",
            args=[(1, 2, (3, b"4", "5"))],
        )
    )
    assert response.abi_return == {"foo": 1, "foo_arc": 2, "child": {"a": 3, "b": b"4", "c": "5"}}

    parent_with_list = (
        (123, 456, (789, b"abc", "def")),
        [(234, b"bcd", "efg")],
    )
    response = call(
        au.AppClientMethodCallParams(
            method="store_tuple",
            args=[parent_with_list],
        )
    )
    assert response.confirmation.confirmed_round, "expected store tuple to succeed"

    response = call(au.AppClientMethodCallParams(method="load_tuple"))
    # New API returns structs with field names
    assert response.abi_return == {
        "parent": {
            "foo": 123,
            "foo_arc": 456,
            "child": {"a": 789, "b": b"abc", "c": "def"},
        },
        "children": [(234, b"bcd", "efg")],
    }

    st = (123, 456)
    box_key = b"box" + b"".join(v.to_bytes(length=8) for v in st)

    response = call(
        au.AppClientMethodCallParams(
            method="store_tuple_in_box",
            args=[st],
            box_references=[box_key],
        )
    )
    assert response.confirmation.confirmed_round, "expected store tuple in box to succeed"

    response = call(
        au.AppClientMethodCallParams(
            method="is_tuple_in_box",
            args=[st],
            box_references=[box_key],
        )
    )
    assert response.abi_return, "expected tuple to be in box"

    response = call(
        au.AppClientMethodCallParams(
            method="load_tuple_from_box",
            args=[st],
            box_references=[box_key],
        )
    )
    assert response.abi_return == {"a": st[0], "b": st[1] + 1}, "expected tuple to load from box"


def test_tuple_storage(deployer: Deployer) -> None:
    client = deployer.create(_TUPLE_SUPPORT_DIR / "tuple_storage.py").client

    # Fund the app
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(200_000),
    )

    client.send.opt_in(
        au.AppClientMethodCallParams(
            method="bootstrap",
            box_references=["box"],
        )
    )

    val = 123
    client.send.call(au.AppClientMethodCallParams(method="mutate_tuple", args=[val]))
    tup_state = client.get_global_state()["tup"]
    assert tup_state.value_raw == _arc4_encode("(uint64[],uint64)", ([0, val], 0))

    val = 234
    client.send.call(
        au.AppClientMethodCallParams(
            method="mutate_box",
            args=[val],
            box_references=["box"],
        )
    )
    box_value = client.get_box_value(b"box")
    assert box_value == _arc4_encode("(uint64[],uint64)", ([0, val], 0))

    val = 2**64 - 1
    client.send.call(au.AppClientMethodCallParams(method="mutate_global", args=[val]))
    glob_state = client.get_global_state()["glob"]
    assert glob_state.value_raw == _arc4_encode("(uint64[],uint64)", ([0, val], 0))

    val = 345
    client.send.call(au.AppClientMethodCallParams(method="mutate_local", args=[val]))
    loc_state = client.get_local_state(deployer.account.addr)["loc"]
    assert loc_state.value_raw == _arc4_encode("(uint64[],uint64)", ([0, val], 0))


def _arc4_encode(arc4_type: str, value: object) -> bytes:
    return abi.ABIType.from_string(arc4_type).encode(value)
