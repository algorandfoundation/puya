import pytest
from algopy import String, UInt64
from algopy_testing import algopy_testing_context
from contract import GovernanceDAO


def _create_contract(quorum: int = 3) -> GovernanceDAO:
    contract = GovernanceDAO()
    contract.create(UInt64(quorum))
    return contract


class TestCreate:
    def test_create_sets_quorum(self) -> None:
        with algopy_testing_context():
            contract = _create_contract(quorum=5)
            assert contract.quorum.value == UInt64(5)


class TestCreateProposal:
    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_returns_sequential_ids(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            id0 = contract.create_proposal(String("Proposal A"))
            id1 = contract.create_proposal(String("Proposal B"))
            assert id0 == 0
            assert id1 == 1

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_stores_proposal_in_boxmap(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("Test Proposal"))
            proposal = contract.proposals[UInt64(0)]
            assert proposal.title == String("Test Proposal")
            assert proposal.yes_votes == UInt64(0)
            assert proposal.no_votes == UInt64(0)
            assert proposal.executed is False
            assert proposal.rejected is False


class TestVote:
    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_vote_updates_yes_tally(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("P"))
            contract.vote(UInt64(0), True)
            proposal = contract.proposals[UInt64(0)]
            assert proposal.yes_votes == UInt64(1)
            assert proposal.no_votes == UInt64(0)

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_vote_updates_no_tally(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("P"))
            contract.vote(UInt64(0), False)
            proposal = contract.proposals[UInt64(0)]
            assert proposal.yes_votes == UInt64(0)
            assert proposal.no_votes == UInt64(1)

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_duplicate_vote_raises_error(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("P"))
            contract.vote(UInt64(0), True)
            with pytest.raises(AssertionError, match="already voted"):
                contract.vote(UInt64(0), False)

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_different_senders_can_vote(self) -> None:
        with algopy_testing_context() as ctx:
            contract = _create_contract()
            contract.create_proposal(String("P"))

            alice = ctx.any.account()
            bob = ctx.any.account()

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.vote(UInt64(0), True)
            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.vote(UInt64(0), False)

            proposal = contract.proposals[UInt64(0)]
            assert proposal.yes_votes == UInt64(1)
            assert proposal.no_votes == UInt64(1)


class TestExecute:
    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_execute_passes_when_yes_majority(self) -> None:
        with algopy_testing_context() as ctx:
            contract = _create_contract(quorum=2)
            contract.create_proposal(String("P"))

            alice = ctx.any.account()
            bob = ctx.any.account()
            charlie = ctx.any.account()

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.vote(UInt64(0), True)
            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.vote(UInt64(0), True)
            with ctx.txn.create_group(active_txn_overrides={"sender": charlie}):
                contract.vote(UInt64(0), False)

            result = contract.execute(UInt64(0))
            assert result is True

            proposal = contract.proposals[UInt64(0)]
            assert proposal.executed is True

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_execute_rejects_when_no_majority(self) -> None:
        with algopy_testing_context() as ctx:
            contract = _create_contract(quorum=2)
            contract.create_proposal(String("P"))

            alice = ctx.any.account()
            bob = ctx.any.account()
            charlie = ctx.any.account()

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.vote(UInt64(0), False)
            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.vote(UInt64(0), False)
            with ctx.txn.create_group(active_txn_overrides={"sender": charlie}):
                contract.vote(UInt64(0), True)

            result = contract.execute(UInt64(0))
            assert result is False

            proposal = contract.proposals[UInt64(0)]
            assert proposal.rejected is True

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_execute_rejects_on_tie(self) -> None:
        with algopy_testing_context() as ctx:
            contract = _create_contract(quorum=2)
            contract.create_proposal(String("P"))

            alice = ctx.any.account()
            bob = ctx.any.account()

            with ctx.txn.create_group(active_txn_overrides={"sender": alice}):
                contract.vote(UInt64(0), True)
            with ctx.txn.create_group(active_txn_overrides={"sender": bob}):
                contract.vote(UInt64(0), False)

            result = contract.execute(UInt64(0))
            assert result is False

    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_execute_quorum_not_met_raises_error(self) -> None:
        with algopy_testing_context():
            contract = _create_contract(quorum=5)
            contract.create_proposal(String("P"))
            contract.vote(UInt64(0), True)
            with pytest.raises(AssertionError, match="quorum not met"):
                contract.execute(UInt64(0))


class TestGetProposal:
    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_returns_correct_proposal(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("My Proposal"))
            result = contract.get_proposal(UInt64(0))
            assert result.title == String("My Proposal")
            assert result.yes_votes == UInt64(0)
            assert result.no_votes == UInt64(0)
            assert result.executed is False
            assert result.rejected is False


class TestGetActiveProposals:
    @pytest.mark.xfail(
        raises=TypeError,
        reason="Array[UInt64]() empty constructor not supported by testing framework",
    )
    def test_returns_active_ids(self) -> None:
        with algopy_testing_context():
            contract = _create_contract()
            contract.create_proposal(String("A"))
            contract.create_proposal(String("B"))
            contract.create_proposal(String("C"))
            active = contract.get_active_proposals()
            assert active.length == 3
            assert active[0] == UInt64(0)
            assert active[1] == UInt64(1)
            assert active[2] == UInt64(2)
