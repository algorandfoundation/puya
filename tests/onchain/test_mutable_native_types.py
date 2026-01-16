import random

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_MUTABLE_NATIVE_TYPES_DIR = TEST_CASES_DIR / "mutable_native_types"


def test_mutable_native_types_abi_call(deployer: Deployer) -> None:
    result = deployer.create((_MUTABLE_NATIVE_TYPES_DIR, "TestAbiCall"))
    client = result.client

    inner_fee = au.AlgoAmount.from_micro_algo(7000)

    call = client.send.call
    call(au.AppClientMethodCallParams(method="test_fixed_struct", static_fee=inner_fee))
    call(au.AppClientMethodCallParams(method="test_nested_struct", static_fee=inner_fee))
    call(au.AppClientMethodCallParams(method="test_dynamic_struct", static_fee=inner_fee))
    call(au.AppClientMethodCallParams(method="test_fixed_array", static_fee=inner_fee))
    call(au.AppClientMethodCallParams(method="test_native_array", static_fee=inner_fee))

    call(
        au.AppClientMethodCallParams(
            method="test_log", static_fee=au.AlgoAmount.from_micro_algo(9000)
        )
    )


def test_mutable_native_types_contract(deployer: Deployer) -> None:
    client = deployer.create((_MUTABLE_NATIVE_TYPES_DIR, "Contract")).client

    call = client.send.call
    call(au.AppClientMethodCallParams(method="test_arr", args=[[]]))
    call(au.AppClientMethodCallParams(method="test_imm_fixed_array"))

    response = call(
        au.AppClientMethodCallParams(method="test_match_struct", args=[{"a": 1, "b": 2}])
    )
    assert response.abi_return is True

    response = call(
        au.AppClientMethodCallParams(method="test_match_struct", args=[{"a": 2, "b": 1}])
    )
    assert response.abi_return is False


@pytest.mark.parametrize(
    "contract_name",
    [
        "Case1WithTups",
        "Case2WithImmStruct",
        "Case3WithStruct",
    ],
)
def test_mutable_native_types(
    deployer: Deployer,
    contract_name: str,
) -> None:
    client = deployer.create((_MUTABLE_NATIVE_TYPES_DIR, contract_name)).client

    # Fund app for boxes
    deployer.localnet.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(2_000_000),
    )

    # Create unauthorized account
    unauthorized = deployer.localnet.account.random()
    deployer.localnet.account.ensure_funded(
        account_to_fund=unauthorized.addr,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )

    def call(
        method: str,
        *,
        args: list[object] | None = None,
        sender: str | None = None,
        signer: au.TransactionSigner | None = None,
    ) -> au.SendAppTransactionResult[au.ABIValue]:
        return client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                args=args,
                box_references=["tup_bag"] * 5,
                note=random.randbytes(8),
                sender=sender,
                signer=signer,
            )
        )

    call("create_box")

    response = call("num_tups")
    assert response.abi_return == 0

    fixed_array_size = 8
    tups = [(i + 1, i + 2) for i in range(fixed_array_size)]

    call("add_tup", args=[tups[0]])
    response = call("num_tups")
    assert response.abi_return == 1

    with pytest.raises(au.LogicError, match="sender not authorized"):
        call("add_tup", args=[tups[0]], sender=unauthorized.addr, signer=unauthorized.signer)

    with pytest.raises(au.LogicError, match="not enough items"):
        call("get_3_tups", args=[0])

    call("add_fixed_tups", args=[tups[1:4]])
    response = call("num_tups")
    assert response.abi_return == 4

    response = call("get_3_tups", args=[0])
    assert response.abi_return == [(i + 1, i + 2) for i in range(3)]

    call("add_many_tups", args=[tups[4:]])
    response = call("num_tups")
    assert response.abi_return == fixed_array_size

    response = call("get_all_tups")
    assert response.abi_return == [(i + 1, i + 2) for i in range(fixed_array_size)]

    with pytest.raises(au.LogicError, match="not enough items"):
        call("get_3_tups", args=[6])

    with pytest.raises(au.LogicError, match="too many tups"):
        call("add_tup", args=[(1, 2)])

    for i in range(8):
        response = call("get_tup", args=[i])
        assert response.abi_return == {"a": tups[i][0], "b": tups[i][1]}

    with pytest.raises(au.LogicError, match="index out of bounds"):
        call("get_tup", args=[8])

    response = call("sum")
    assert response.abi_return == sum(i + 1 + i + 2 for i in range(fixed_array_size))

    call("set_a", args=[1])

    response = call("sum")
    assert response.abi_return == sum(1 + i + 2 for i in range(fixed_array_size))

    call("set_b", args=[1])

    response = call("sum")
    assert response.abi_return == sum(1 + 1 for _ in range(fixed_array_size))

    response = call("get_3_tups", args=[5])
    assert response.abi_return == [(1, 1) for _ in range(3)]


def test_mutable_native_types_itxn_abi_call(deployer: Deployer) -> None:
    client = deployer.create((_MUTABLE_NATIVE_TYPES_DIR, "TestItxnAbiCall")).client

    def call(method: str, num_txns: int = 7) -> None:
        client.send.call(
            au.AppClientMethodCallParams(
                method=method,
                static_fee=au.AlgoAmount.from_micro_algo(1000) * num_txns,
            )
        )

    call("test_fixed_struct")
    call("test_nested_struct")
    call("test_dynamic_struct")
    call("test_fixed_array")
    call("test_native_array")
    call("test_log", num_txns=9)
