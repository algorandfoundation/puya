from collections.abc import Generator

import algopy
import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from .contract import VotingContract


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


@pytest.mark.usefixtures("context")
def test_set_topic() -> None:
    # Arrange
    contract = VotingContract()
    topic = algopy.Bytes(b"New Topic")

    # Act
    contract.set_topic(topic)

    # Assert
    assert contract.topic.value == topic


def test_vote(context: AlgopyTestContext) -> None:
    # Arrange
    contract = VotingContract()
    contract.votes.value = algopy.UInt64(0)
    voter = context.default_creator

    context.set_transaction_group(
        gtxn=[
            context.any_application_call_transaction(
                sender=voter,
                app_id=context.any_application(),
                app_args=[algopy.Bytes(b"vote"), voter.bytes],
            ),
            context.any_payment_transaction(
                sender=voter,
                amount=algopy.UInt64(10_000),
            ),
        ],
        active_transaction_index=0,
    )

    # Act
    result = contract.approval_program()

    # Assert
    assert result == algopy.UInt64(1)
    assert contract.votes.value == algopy.UInt64(1)
    assert contract.voted[voter] == algopy.UInt64(1)


def test_vote_already_voted(context: AlgopyTestContext) -> None:
    # Arrange
    contract = VotingContract()
    voter = context.any_account()
    contract.voted[voter] = algopy.UInt64(1)
    context.patch_txn_fields(sender=voter)

    context.set_transaction_group(
        gtxn=[
            context.any_application_call_transaction(
                sender=voter,
                app_id=context.any_application(),
                app_args=[algopy.Bytes(b"vote"), voter.bytes],
            ),
            context.any_payment_transaction(
                sender=voter,
                amount=algopy.UInt64(10_000),
            ),
        ],
        active_transaction_index=0,
    )

    # Act
    result = contract.vote(voter)

    # Assert
    assert result is False
    assert contract.votes.value == algopy.UInt64(0)


@pytest.mark.usefixtures("context")
def test_get_votes_subroutine() -> None:
    # Arrange
    contract = VotingContract()
    contract.votes.value = algopy.UInt64(10)

    # Act
    votes = contract.get_votes()

    # Assert
    assert votes == algopy.UInt64(10)


@pytest.mark.usefixtures("context")
def test_clear_state_program() -> None:
    # Act
    contract = VotingContract()

    # Assert
    assert contract.clear_state_program() == algopy.UInt64(1)
