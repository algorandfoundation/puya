"""Example 10: Multi-Txn Distributor

This example demonstrates grouped inner transactions and outer group transaction access.

Features:
- itxn.submit_txns() with typed tuple return (fixed-size grouped inner transactions)
- itxn.Payment().stage() / itxn.submit_staged() (dynamic-size grouped inner transactions)
- gtxn.PaymentTransaction params (reading fields from outer group transactions)
- op.GITxn for verifying submitted group fields

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import (
    Account,
    ARC4Contract,
    Global,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
    urange,
)


# example: MULTI_TXN_DISTRIBUTOR
class MultiTxnDistributor(ARC4Contract):
    """Contract that distributes funds to multiple recipients via grouped inner transactions."""

    @arc4.abimethod
    def distribute_fixed(
        self,
        funds: gtxn.PaymentTransaction,
        receiver1: Account,
        receiver2: Account,
        receiver3: Account,
    ) -> tuple[UInt64, UInt64, UInt64]:
        """Distribute equal payment to exactly three recipients using itxn.submit_txns.

        Demonstrates typed tuple return - each element is strongly typed.

        Args:
            funds: the outer group payment transaction funding the distribution
            receiver1: first recipient account
            receiver2: second recipient account
            receiver3: third recipient account

        Returns:
            Tuple of amounts sent to each recipient.
        """
        assert funds.receiver == Global.current_application_address, "funds must be sent to app"

        share = funds.amount // UInt64(3)

        pay1 = itxn.Payment(receiver=receiver1, amount=share)
        pay2 = itxn.Payment(receiver=receiver2, amount=share)
        pay3 = itxn.Payment(receiver=receiver3, amount=share)

        txn1, txn2, txn3 = itxn.submit_txns(pay1, pay2, pay3)

        return txn1.amount, txn2.amount, txn3.amount

    @arc4.abimethod
    def distribute_dynamic(
        self,
        funds: gtxn.PaymentTransaction,
        receivers: arc4.DynamicArray[arc4.Address],
    ) -> UInt64:
        """Distribute funds to a dynamic list of recipients using stage/submit_staged.

        Demonstrates .stage(begin_group=True) / .stage() / submit_staged() for
        variable-size groups, and op.GITxn for verifying submitted group fields.

        Args:
            funds: the outer group payment transaction funding the distribution
            receivers: dynamic array of recipient addresses

        Returns:
            The per-recipient share amount.
        """
        assert funds.receiver == Global.current_application_address, "funds must be sent to app"

        count = receivers.length
        assert count > 0, "must have at least one receiver"

        share = funds.amount // count

        itxn.Payment(
            receiver=receivers[0].native,
            amount=share,
        ).stage(begin_group=True)

        for i in urange(1, count):
            itxn.Payment(
                receiver=receivers[i].native,
                amount=share,
            ).stage()

        itxn.submit_staged()

        # Verify first payment via op.GITxn
        assert op.GITxn.amount(0) == share, "first payment amount correct"

        return share


# example: MULTI_TXN_DISTRIBUTOR
