import random

import algokit_utils as au
import pytest
from algokit_abi import abi

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer

_REFERENCE_BOX = EXAMPLES_DIR / "devportal" / "reference_box"

# COUNTER_BOX_MBR: 2500 + (39 key + 8 value) * 400 = 21300
_EXPECTED_BOX_MBR = 2_500 + (7 + 32 + 8) * 400

_ADDRESS = abi.ABIType.from_string("address")


def _counter_box_ref(addr: str) -> au.BoxReference:
    """BoxMap(Account, ..., key_prefix="counter") stores under
    b"counter" + <32-byte raw address>."""
    return au.BoxReference(0, b"counter" + _ADDRESS.encode(addr))


def _deploy(deployer: Deployer) -> au.AppClient:
    """Deploy ReferenceBox and fund the app account with the base account MBR
    so it can later hold box storage. Per-box MBR is still funded by the
    grouped payment inside increment_box_counter."""
    client = deployer.create(_REFERENCE_BOX).client
    deployer.localnet.send.payment(
        au.PaymentParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(100_000),
        )
    )
    return client


def test_get_box_mbr_quotes_constant(deployer: Deployer) -> None:
    client = _deploy(deployer)

    # the MBR is a compile-time constant of the fixed box layout; the readonly
    # getter lets clients quote it instead of hard-coding the number
    mbr = client.send.call(au.AppClientMethodCallParams(method="get_box_mbr", args=[])).abi_return
    assert mbr == _EXPECTED_BOX_MBR


def test_increment_box_counter_creates_and_increments(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)
    box_ref = _counter_box_ref(account.addr)

    # counter starts unset -> reads back as 0
    initial = client.send.call(
        au.AppClientMethodCallParams(method="get_box_counter", args=[])
    ).abi_return
    assert initial == 0

    def increment() -> object:
        # grouped [Payment(MBR) -> AppCall]; the payment is the typed ABI arg
        pay = au.PaymentParams(
            sender=account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(_EXPECTED_BOX_MBR),
            note=random.randbytes(8),
        )
        result = client.send.call(
            au.AppClientMethodCallParams(
                method="increment_box_counter",
                args=[pay],
                box_references=[box_ref],
                note=random.randbytes(8),
            )
        )
        return result.abi_return

    assert increment() == 1
    assert increment() == 2
    assert increment() == 3

    # the readonly getter agrees with the latest value
    current = client.send.call(
        au.AppClientMethodCallParams(method="get_box_counter", args=[], box_references=[box_ref])
    ).abi_return
    assert current == 3


def test_get_box_counter_for_account(
    deployer: Deployer, localnet: au.AlgorandClient, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)
    box_ref = _counter_box_ref(account.addr)

    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(_EXPECTED_BOX_MBR),
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="increment_box_counter",
            args=[pay],
            box_references=[box_ref],
        )
    )

    # looked up by explicit account argument
    value = client.send.call(
        au.AppClientMethodCallParams(
            method="get_box_counter_for_account",
            args=[account.addr],
            box_references=[box_ref],
        )
    ).abi_return
    assert value == 1

    # an account that never incremented reads back as 0
    other = localnet.account.random()
    other_value = client.send.call(
        au.AppClientMethodCallParams(
            method="get_box_counter_for_account",
            args=[other.addr],
            box_references=[_counter_box_ref(other.addr)],
        )
    ).abi_return
    assert other_value == 0


def test_increment_box_counter_mbr_only_required_on_creation(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)
    box_ref = _counter_box_ref(account.addr)

    # first increment creates the box, so the payment must fund the MBR
    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(_EXPECTED_BOX_MBR),
    )
    first = client.send.call(
        au.AppClientMethodCallParams(
            method="increment_box_counter",
            args=[pay],
            box_references=[box_ref],
        )
    ).abi_return
    assert first == 1

    # the box already exists, so a zero-amount payment is accepted
    zero_pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(0),
        note=random.randbytes(8),
    )
    second = client.send.call(
        au.AppClientMethodCallParams(
            method="increment_box_counter",
            args=[zero_pay],
            box_references=[box_ref],
            note=random.randbytes(8),
        )
    ).abi_return
    assert second == 2


def test_increment_box_counter_wrong_payment_amount_is_rejected(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)
    box_ref = _counter_box_ref(account.addr)

    # payment does not cover the box MBR
    pay = au.PaymentParams(
        sender=account.addr,
        receiver=client.app_address,
        amount=au.AlgoAmount.from_micro_algo(_EXPECTED_BOX_MBR - 1),
    )
    with pytest.raises(au.LogicError, match="Payment must cover the box MBR"):
        client.send.call(
            au.AppClientMethodCallParams(
                method="increment_box_counter",
                args=[pay],
                box_references=[box_ref],
            )
        )


def test_increment_box_counter_wrong_receiver_is_rejected(
    deployer: Deployer, account: au.AddressWithSigners
) -> None:
    client = _deploy(deployer)
    box_ref = _counter_box_ref(account.addr)

    # payment goes to the caller instead of the contract
    pay = au.PaymentParams(
        sender=account.addr,
        receiver=account.addr,
        amount=au.AlgoAmount.from_micro_algo(_EXPECTED_BOX_MBR),
    )
    with pytest.raises(au.LogicError, match="Payment must be to the contract"):
        client.send.call(
            au.AppClientMethodCallParams(
                method="increment_box_counter",
                args=[pay],
                box_references=[box_ref],
            )
        )
