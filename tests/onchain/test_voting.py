import math
import random
import time

import algokit_utils as au
from algokit_common import public_key_from_address
from nacl.signing import SigningKey

from tests import EXAMPLES_DIR
from tests.utils.deployer import Deployer


def test_voting_app(deployer: Deployer) -> None:
    algorand = deployer.localnet
    creator_account = deployer.account

    # Create a separate voter account
    voter_account = algorand.account.random()
    algorand.account.ensure_funded(
        account_to_fund=voter_account.addr,
        dispenser_account=creator_account,
        min_spending_balance=au.AlgoAmount.from_micro_algo(10_000_000),
    )

    private_key = SigningKey.generate()

    # "dev mode" does not have regular block generation, only "on demand".
    # The max timestamp advancement between blocks is a consensus parameter which currently is 25s.
    # So effectively, the current block timestamp could be any point in the past, and could
    # rapidly advance in 25s increments - but cannot be in the future.
    # So to ensure the voting window remains open for this test, we start at the current timestamp
    # and use the actual time plus a voting window of a thousand seconds.
    algod = algorand.client.algod
    start_time = algod.block(algod.status().last_round).block.header.timestamp
    epoch = int(time.time())
    end_time = epoch + 1000

    quorum = math.ceil(random.randint(1, 9) * 1000)
    question_counts = [1] * 10

    # Create the voting app
    client = deployer.create(
        EXAMPLES_DIR / "voting",
        method="create",
        args={
            "vote_id": "1",
            "metadata_ipfs_cid": "cid",
            "start_time": start_time,
            "end_time": end_time,
            "quorum": quorum,
            "snapshot_public_key": private_key.verify_key.encode(),
            "nft_image_url": "ipfs://cid",
            "option_counts": question_counts,
        },
    ).client

    # Bootstrap with payment
    bootstrap_payment = algorand.create_transaction.payment(
        au.PaymentParams(
            sender=creator_account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo((100000 * 2) + 1000 + 2500 + 400 * (1 + 8 * 10)),
            note=b"Bootstrap payment",
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="bootstrap",
            args=[bootstrap_payment],
            box_references=["V"],
        )
    )

    def get_account_signature(voter_public_key: bytes) -> bytes:
        signed = private_key.sign(voter_public_key)
        return signed.signature

    voter_public_key = public_key_from_address(voter_account.addr)

    # Check preconditions before voting
    pre_conditions = client.send.call(
        au.AppClientMethodCallParams(
            method="get_preconditions",
            args=[get_account_signature(voter_public_key)],
            box_references=[voter_public_key],
            sender=voter_account.addr,
            signer=voter_account.signer,
            static_fee=au.AlgoAmount.from_micro_algo(4000),
        )
    )
    assert pre_conditions.abi_return is not None
    assert isinstance(pre_conditions.abi_return, dict)
    assert pre_conditions.abi_return["is_voting_open"] == 1
    assert pre_conditions.abi_return["is_allowed_to_vote"] == 1  # allowed
    assert pre_conditions.abi_return["has_already_voted"] == 0  # no

    # Vote
    vote_payment = algorand.create_transaction.payment(
        au.PaymentParams(
            sender=voter_account.addr,
            receiver=client.app_address,
            amount=au.AlgoAmount.from_micro_algo(400 * (32 + 2 + 10) + 2500),
            note=b"Vote payment",
        )
    )
    client.send.call(
        au.AppClientMethodCallParams(
            method="vote",
            args=[vote_payment, get_account_signature(voter_public_key), [0] * 10],
            box_references=["V", voter_public_key],
            sender=voter_account.addr,
            signer=voter_account.signer,
            static_fee=au.AlgoAmount.from_micro_algo(12000),
        )
    )

    # Check preconditions after voting
    pre_conditions = client.send.call(
        au.AppClientMethodCallParams(
            method="get_preconditions",
            args=[get_account_signature(voter_public_key)],
            box_references=[voter_public_key],
            sender=voter_account.addr,
            signer=voter_account.signer,
            static_fee=au.AlgoAmount.from_micro_algo(4000),
        )
    )
    assert pre_conditions.abi_return is not None
    assert isinstance(pre_conditions.abi_return, dict)
    assert pre_conditions.abi_return["is_voting_open"] == 1
    assert pre_conditions.abi_return["is_allowed_to_vote"] == 1  # allowed
    assert pre_conditions.abi_return["has_already_voted"] == 1  # voted

    # Close voting
    client.send.call(
        au.AppClientMethodCallParams(
            method="close",
            box_references=["V"],
            sender=creator_account.addr,
            signer=creator_account.signer,
            static_fee=au.AlgoAmount.from_micro_algo(1_000_000),
        )
    )

    # Check preconditions after close
    creator_public_key = public_key_from_address(creator_account.addr)
    pre_conditions = client.send.call(
        au.AppClientMethodCallParams(
            method="get_preconditions",
            args=[get_account_signature(voter_public_key)],
            box_references=[creator_public_key],
            static_fee=au.AlgoAmount.from_micro_algo(4000),
        )
    )
    assert pre_conditions.abi_return is not None
    assert isinstance(pre_conditions.abi_return, dict)
    assert pre_conditions.abi_return["is_voting_open"] == 0
