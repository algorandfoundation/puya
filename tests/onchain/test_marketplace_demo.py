import algokit_utils as au
from algokit_abi import abi

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


# see https://github.com/algorandfoundation/puya-ts-demo/blob/main/contracts/marketplace/marketplace.test.ts
def test_marketplace_with_tups(deployer: Deployer, asset_a: int) -> None:
    result = deployer.create((TEST_CASES_DIR / "marketplace_demo", "DigitalMarketplaceWithTups"))
    client = result.client
    algorand = deployer.localnet

    # Fund app for minimum balance requirements
    algorand.account.ensure_funded(
        account_to_fund=client.app_address,
        dispenser_account=deployer.account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(100_000),
    )

    # Optin to receive asset
    mbr_pay = algorand.create_transaction.payment(
        au.PaymentParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(100_000),
            note=b"minimum balance to optin to an asset",
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="allowAsset",
            args=[mbr_pay, asset_a],
            static_fee=au.AlgoAmount.from_micro_algo(2000),
        )
    )

    # Test parameters for the application call
    nonce = 1
    unitary_price = 1
    deposited = 10

    # Create payment and asset transfer transactions
    mbr_pay = algorand.create_transaction.payment(
        au.PaymentParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(50500),
            note=b"firstDeposit payment",
        )
    )
    xfer = algorand.create_transaction.asset_transfer(
        au.AssetTransferParams(
            sender=deployer.account.addr,
            receiver=client.app_address,
            amount=deposited,
            asset_id=asset_a,
        )
    )

    # The application call needs to know which boxes will be used
    box_key = b"listings" + _arc4_encode(
        "(address,uint64,uint64)", (deployer.account.addr, asset_a, nonce)
    )

    # Make the app call
    client.send.call(
        au.AppClientMethodCallParams(
            method="firstDeposit",
            args=[mbr_pay, xfer, unitary_price, nonce],
            box_references=[(1).to_bytes(8), box_key],
        )
    )

    # Assert the deposited value is as expected
    box_value = client.get_box_value_from_abi_type(
        box_key, client.app_spec.structs["ListingValue"]
    )
    assert isinstance(box_value, dict)
    assert box_value["deposited"] == deposited


def _arc4_encode(arc4_type: str, value: object) -> bytes:
    return abi.ABIType.from_string(arc4_type).encode(value)
