"""
Example 05: Membership Registry

This example demonstrates local state management with opt-in and close-out lifecycle.

Features:
- GlobalState for tracking member counts
- LocalState for per-member data (nickname, joined round)
- Opt-in lifecycle (baremethod with OptIn)
- Close-out lifecycle (baremethod with CloseOut)
- Txn.sender and op.Global.round

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import Account, ARC4Contract, GlobalState, LocalState, String, Txn, UInt64, arc4, op


# example: MEMBERSHIP_REGISTRY
# Membership registry contract — users opt in to register and close out to leave
class MembershipRegistry(ARC4Contract):
    """Manages member registration via LocalState with opt-in/close-out lifecycle."""

    def __init__(self) -> None:
        # GlobalState tracking the total number of registered members
        self.member_count = GlobalState(UInt64(0))
        # LocalState storing the member's chosen nickname
        self.nickname = LocalState(String, key="nickname")
        # LocalState storing the round number when the member joined
        self.joined_round = LocalState(UInt64, key="joined_round")

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        """Opt-in handler — registers the caller as a member.

        Guards against double opt-in by checking if the sender already has local state.
        """
        assert not self.nickname.maybe(Txn.sender)[1], "already a member"
        self.nickname[Txn.sender] = String("")
        self.joined_round[Txn.sender] = op.Global.round
        self.member_count.value += 1

    @arc4.baremethod(allow_actions=["CloseOut"])
    def close_out(self) -> None:
        """Close-out handler — removes the caller from the registry."""
        self.member_count.value -= 1

    @arc4.abimethod
    def set_nickname(self, name: String) -> None:
        """Set the caller's nickname.

        Args:
            name: the new nickname to store
        """
        self.nickname[Txn.sender] = name

    @arc4.abimethod(readonly=True)
    def get_nickname(self, member: Account) -> String:
        """Read a member's nickname.

        Args:
            member: the account to look up

        Returns:
            the member's nickname
        """
        return self.nickname[member]

    @arc4.abimethod(readonly=True)
    def get_joined_round(self, member: Account) -> UInt64:
        """Read the round a member joined.

        Args:
            member: the account to look up

        Returns:
            the round number when the member registered
        """
        return self.joined_round[member]

    @arc4.abimethod(readonly=True)
    def get_member_count(self) -> UInt64:
        """Read the current total number of registered members.

        Returns:
            the member count
        """
        return self.member_count.value


# example: MEMBERSHIP_REGISTRY
