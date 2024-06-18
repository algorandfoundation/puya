from algopy import (
    Account,
    Bytes,
    Contract,
    GlobalState,
    LocalState,
    TransactionType,
    Txn,
    UInt64,
    op,
    subroutine,
)

VOTE_PRICE = 10_000


class VotingContract(Contract):
    def __init__(self) -> None:
        self.topic = GlobalState(Bytes(b"default_topic"), key="topic", description="Voting topic")
        self.votes = GlobalState(
            UInt64(0),
            key="votes",
            description="Votes for the option",
        )
        self.voted = LocalState(UInt64, key="voted", description="Tracks if an account has voted")

    @subroutine
    def set_topic(self, topic: Bytes) -> None:
        self.topic.value = topic

    @subroutine
    def vote(self, voter: Account) -> bool:
        assert op.Global.group_size == UInt64(2)
        assert op.GTxn.amount(1) == UInt64(VOTE_PRICE)
        assert op.GTxn.type_enum(1) == TransactionType.Payment
        _value, exists = self.voted.maybe(voter)
        if exists:
            return False  # Already voted
        self.votes.value += UInt64(1)
        self.voted[voter] = UInt64(1)
        return True

    @subroutine
    def get_votes(self) -> UInt64:
        return self.votes.value

    def approval_program(self) -> UInt64:
        if Txn.application_args(0) == b"set_topic":
            self.set_topic(Txn.application_args(1))
            return UInt64(1)
        elif Txn.application_args(0) == b"vote":
            return UInt64(1) if self.vote(Txn.sender) else UInt64(0)
        elif Txn.application_args(0) == b"get_votes":
            return self.votes.value
        return UInt64(0)

    def clear_state_program(self) -> bool:
        return True
