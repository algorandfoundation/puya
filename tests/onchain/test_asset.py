import re

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer


def test_asset(deployer_o: Deployer, asset_a: int, asset_b: int) -> None:
    result = deployer_o.create_bare(TEST_CASES_DIR / "asset")
    client = result.client
    app_address = client.app_address

    # Fund app to meet minimum balance requirements
    deployer_o.localnet.send.payment(
        au.PaymentParams(
            sender=deployer_o.account.addr,
            receiver=app_address,
            amount=au.AlgoAmount.from_micro_algo(200_000),
        )
    )

    # Increased fee to cover opt_in inner txn
    inner_fee = au.AlgoAmount.from_micro_algo(2000)

    # Call opt_in
    client.send.bare.call(
        au.AppClientBareCallParams(
            args=[b"opt_in"],
            asset_references=[asset_a],
            static_fee=inner_fee,
        )
    )

    # Call is_opted_in with correct asset
    client.send.bare.call(
        au.AppClientBareCallParams(
            args=[b"is_opted_in"],
            asset_references=[asset_a],
        )
    )

    # Call is_opted_in with wrong asset - should fail
    with pytest.raises(au.LogicError, match=re.escape("asset self.asa == asset")):
        client.send.bare.call(
            au.AppClientBareCallParams(
                args=[b"is_opted_in"],
                asset_references=[asset_b],
            )
        )
