from collections.abc import Sequence

import algokit_utils as au

from tests import TEST_CASES_DIR
from tests.utils.compile import compile_arc56
from tests.utils.deployer import Deployer

_GROUP_SIDE_EFFECTS_DIR = TEST_CASES_DIR / "group_side_effects"


def test_group_side_effects(deployer: Deployer) -> None:
    algorand = deployer.localnet

    # Get other app spec (don't deploy yet - main contract will create it)
    other_app_spec = compile_arc56(_GROUP_SIDE_EFFECTS_DIR / "other.py")

    # Create main app
    client = deployer.create(_GROUP_SIDE_EFFECTS_DIR / "contract.py").client

    # Create asset create transaction
    asset_create_txn = algorand.create_transaction.asset_create(
        au.AssetCreateParams(
            sender=deployer.account.addr,
            total=10_000_000,
            decimals=0,
            default_frozen=False,
            asset_name="asset group",
            unit_name="AGRP",
        )
    )

    # Create app factory for "other" app to build app create transaction
    other_factory = au.AppFactory(
        au.AppFactoryParams(
            algorand=algorand,
            app_spec=other_app_spec,
            default_sender=deployer.account.addr,
            default_signer=deployer.account.signer,
        )
    )

    # Build app create transaction
    app_create_txn = other_factory.create_transaction.bare.create(au.AppFactoryCreateParams())

    # Call app with create txns
    response = client.send.call(
        au.AppClientMethodCallParams(
            method="create_group",
            args=[asset_create_txn, app_create_txn],
        )
    )
    assert isinstance(response.abi_return, Sequence)
    asset_id, other_app_id = response.abi_return

    # Create app client for the other app with the deployed app_id
    other_client = au.AppClient(
        au.AppClientParams(
            app_spec=other_app_spec,
            app_id=other_app_id,
            algorand=algorand,
            default_sender=deployer.account.addr,
            default_signer=deployer.account.signer,
        )
    )

    built = other_client.create_transaction.call(au.AppClientMethodCallParams(method="some_value"))
    app_call_txn = built.transactions[0]

    client.send.call(
        au.AppClientMethodCallParams(
            method="log_group",
            args=[app_call_txn],
        )
    )
