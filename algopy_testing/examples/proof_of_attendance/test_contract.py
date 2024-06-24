from collections.abc import Generator

import algopy
import algosdk
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from .contract import ProofOfAttendance


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_init(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ProofOfAttendance()
    max_attendees = context.any_uint64(1, 100)

    # Act
    contract.init(max_attendees)

    # Assert
    assert contract.max_attendees == max_attendees


def test_confirm_attendance(
    context: AlgopyTestContext,
) -> None:
    # Arrange
    contract = ProofOfAttendance()
    contract.max_attendees = context.any_uint64(1, 100)

    # Act
    contract.confirm_attendance()

    # Assert
    assert context.get_box(context.default_creator.bytes) == algopy.op.itob(1)


def test_claim_poa(context: AlgopyTestContext) -> None:
    # Arrange
    contract = ProofOfAttendance()
    dummy_poa = context.any_asset()
    opt_in_txn = context.any_asset_transfer_transaction(
        sender=context.default_creator,
        asset_receiver=context.default_creator,
        asset_close_to=algopy.Account(algosdk.constants.ZERO_ADDRESS),
        rekey_to=algopy.Account(algosdk.constants.ZERO_ADDRESS),
        xfer_asset=dummy_poa,
        fee=algopy.UInt64(0),
        asset_amount=algopy.UInt64(0),
    )
    context.set_box(context.default_creator.bytes, algopy.op.itob(dummy_poa.id))

    # Act
    contract.claim_poa(opt_in_txn)

    # Assert
    axfer_itxn = context.get_submitted_itxn_group(-1).asset_transfer(0)
    assert axfer_itxn.asset_receiver == context.default_creator
    assert axfer_itxn.asset_amount == algopy.UInt64(1)
