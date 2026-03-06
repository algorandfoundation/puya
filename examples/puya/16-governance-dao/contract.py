"""Example 16: Governance DAO

This example demonstrates a full DAO proposal lifecycle using Box/BoxMap storage.

Features:
- BoxMap<UInt64, Proposal> — proposals keyed by numeric ID
- Box<arc4.DynamicArray> — dynamically built list of active proposal IDs
- arc4.Struct — Proposal record with typed fields (module scope)
- Vote deduplication via composite byte keys (proposalId + voter address)
- arc4.DynamicArray<arc4.UInt64> — tracking active proposals
- ensure_budget() / OpUpFeeSource — opcode budget management
- Full lifecycle: create → propose → vote → execute

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import (
    ARC4Contract,
    Box,
    BoxMap,
    GlobalState,
    OpUpFeeSource,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    op,
)


class Proposal(arc4.Struct):
    """On-chain proposal record stored in BoxMap — fields as arc4 types."""

    title: arc4.String
    creator: arc4.Address
    yes_votes: arc4.UInt64
    no_votes: arc4.UInt64
    executed: arc4.Bool
    rejected: arc4.Bool


# example: GOVERNANCE_DAO
class GovernanceDAO(ARC4Contract):
    """Governance DAO with Box/BoxMap storage for proposals and vote deduplication."""

    def __init__(self) -> None:
        self.proposal_count = GlobalState(UInt64(0))
        self.quorum = GlobalState(UInt64(0))
        self.proposals = BoxMap(UInt64, Proposal, key_prefix="p_")
        self.active_proposals = Box(arc4.DynamicArray[arc4.UInt64], key="active")

    @arc4.abimethod(create="require")
    def create(self, quorum: UInt64) -> None:
        """Deploy and configure the DAO with a quorum threshold.

        Args:
            quorum: minimum total votes required to execute a proposal
        """
        self.quorum.value = quorum

    @arc4.abimethod
    def create_proposal(self, title: arc4.String) -> UInt64:
        """Submit a new proposal and track it in the active proposals list.

        Args:
            title: human-readable proposal title

        Returns:
            the newly assigned proposal ID
        """
        ensure_budget(2000, fee_source=OpUpFeeSource.Any)
        proposal_id = self.proposal_count.value
        self.proposals[proposal_id] = Proposal(
            title=title,
            creator=arc4.Address(Txn.sender),
            yes_votes=arc4.UInt64(0),
            no_votes=arc4.UInt64(0),
            executed=arc4.Bool(False),
            rejected=arc4.Bool(False),
        )
        # Track active proposals using arc4.DynamicArray
        if bool(self.active_proposals):
            active = self.active_proposals.value.copy()
            del self.active_proposals.value
        else:
            active = arc4.DynamicArray[arc4.UInt64]()
        active.append(arc4.UInt64(proposal_id))
        self.active_proposals.value = active.copy()

        self.proposal_count.value = proposal_id + 1
        return proposal_id

    @arc4.abimethod
    def vote(self, proposal_id: UInt64, in_favor: bool) -> None:
        """Cast a yes/no vote on an open proposal with deduplication.

        Args:
            proposal_id: the ID of the proposal to vote on
            in_favor: True for yes, False for no
        """
        ensure_budget(2000, fee_source=OpUpFeeSource.Any)
        assert proposal_id in self.proposals, "proposal not found"
        proposal = self.proposals[proposal_id].copy()
        assert not proposal.executed.native, "already executed"
        assert not proposal.rejected.native, "already rejected"

        # Vote deduplication via Box — composite key: proposalId + voter address
        vote_key = b"v" + op.itob(proposal_id) + Txn.sender.bytes
        vote_len, vote_exists = op.Box.length(vote_key)
        assert not vote_exists, "already voted"
        op.Box.put(vote_key, op.itob(UInt64(1) if in_favor else UInt64(0)))

        # Update tally
        if in_favor:
            proposal.yes_votes = arc4.UInt64(proposal.yes_votes.as_uint64() + 1)
        else:
            proposal.no_votes = arc4.UInt64(proposal.no_votes.as_uint64() + 1)
        self.proposals[proposal_id] = proposal.copy()

    @arc4.abimethod(readonly=True)
    def get_proposal(self, proposal_id: UInt64) -> Proposal:
        """Read a proposal by ID.

        Args:
            proposal_id: the ID of the proposal to read

        Returns:
            the Proposal struct
        """
        return self.proposals[proposal_id]

    @arc4.abimethod(readonly=True)
    def get_active_proposals(self) -> arc4.DynamicArray[arc4.UInt64]:
        """Return the list of all active proposal IDs.

        Returns:
            arc4.DynamicArray of proposal IDs
        """
        return self.active_proposals.value.copy()

    @arc4.abimethod
    def execute(self, proposal_id: UInt64) -> bool:
        """Execute a proposal that reached quorum; marks as executed or rejected.

        Args:
            proposal_id: the ID of the proposal to execute

        Returns:
            True if the proposal passed, False if rejected
        """
        ensure_budget(2000, fee_source=OpUpFeeSource.Any)
        assert proposal_id in self.proposals, "proposal not found"
        proposal = self.proposals[proposal_id].copy()
        assert not proposal.executed.native, "already executed"
        assert not proposal.rejected.native, "already rejected"

        total_votes = proposal.yes_votes.as_uint64() + proposal.no_votes.as_uint64()
        assert total_votes >= self.quorum.value, "quorum not met"

        if proposal.yes_votes.as_uint64() > proposal.no_votes.as_uint64():
            proposal.executed = arc4.Bool(True)
            self.proposals[proposal_id] = proposal.copy()
            return True
        else:
            proposal.rejected = arc4.Bool(True)
            self.proposals[proposal_id] = proposal.copy()
            return False


# example: GOVERNANCE_DAO
