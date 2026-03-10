"""Example 16: Governance DAO

This example demonstrates a full DAO proposal lifecycle using Box/BoxMap storage.

Features:
- BoxMap<UInt64, Proposal> — proposals keyed by numeric ID
- Box<Array> — dynamically built list of active proposal IDs
- Struct — Proposal record with typed fields (module scope)
- Vote deduplication via composite byte keys (proposalId + voter address)
- Array[UInt64] — tracking active proposals
- ensure_budget() / OpUpFeeSource — opcode budget management
- Full lifecycle: create → propose → vote → execute

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import (
    Account,
    ARC4Contract,
    Array,
    Box,
    BoxMap,
    GlobalState,
    OpUpFeeSource,
    String,
    Struct,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    op,
)


class Proposal(Struct):
    """On-chain proposal record stored in BoxMap — fields as native types."""

    title: String
    creator: Account
    yes_votes: UInt64
    no_votes: UInt64
    executed: bool
    rejected: bool


# example: GOVERNANCE_DAO
class GovernanceDAO(ARC4Contract):
    """Governance DAO with Box/BoxMap storage for proposals and vote deduplication."""

    def __init__(self) -> None:
        self.proposal_count = GlobalState(UInt64(0))
        self.quorum = GlobalState(UInt64(0))
        self.proposals = BoxMap(UInt64, Proposal, key_prefix="p_")
        self.active_proposals = Box(Array[UInt64], key="active")

    @arc4.abimethod(create="require")
    def create(self, quorum: UInt64) -> None:
        """Deploy and configure the DAO with a quorum threshold.

        Args:
            quorum: minimum total votes required to execute a proposal
        """
        self.quorum.value = quorum

    @arc4.abimethod
    def create_proposal(self, title: String) -> UInt64:
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
            creator=Txn.sender,
            yes_votes=UInt64(0),
            no_votes=UInt64(0),
            executed=False,
            rejected=False,
        )
        # Track active proposals using Array
        if bool(self.active_proposals):
            active = self.active_proposals.value.copy()
            del self.active_proposals.value
        else:
            active = Array[UInt64]()
        active.append(proposal_id)
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
        assert not proposal.executed, "already executed"
        assert not proposal.rejected, "already rejected"

        # Vote deduplication via Box — composite key: proposalId + voter address
        vote_key = b"v" + op.itob(proposal_id) + Txn.sender.bytes
        vote_len, vote_exists = op.Box.length(vote_key)
        assert not vote_exists, "already voted"
        op.Box.put(vote_key, op.itob(UInt64(1) if in_favor else UInt64(0)))

        # Update tally
        if in_favor:
            proposal.yes_votes += 1
        else:
            proposal.no_votes += 1
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
    def get_active_proposals(self) -> Array[UInt64]:
        """Return the list of all active proposal IDs.

        Returns:
            Array of proposal IDs
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
        assert not proposal.executed, "already executed"
        assert not proposal.rejected, "already rejected"

        total_votes = proposal.yes_votes + proposal.no_votes
        assert total_votes >= self.quorum.value, "quorum not met"

        if proposal.yes_votes > proposal.no_votes:
            proposal.executed = True
            self.proposals[proposal_id] = proposal.copy()
            return True
        else:
            proposal.rejected = True
            self.proposals[proposal_id] = proposal.copy()
            return False


# example: GOVERNANCE_DAO
