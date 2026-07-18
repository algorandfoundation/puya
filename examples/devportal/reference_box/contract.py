from algopy import (
    Account,
    ARC4Contract,
    BoxMap,
    Global,
    Txn,
    UInt64,
    arc4,
    gtxn,
)

# example: REFERENCE_BOX_EXAMPLE
# Box MBR (minimum balance requirement) is a protocol-defined function of
# key + value size, so for a fixed box layout it is a compile-time constant.
BOX_MBR_BASE = 2_500  # microAlgo flat cost per box
BOX_MBR_PER_BYTE = 400  # microAlgo per byte of key + value
COUNTER_BOX_KEY_LENGTH = 7 + 32  # len(b"counter") key prefix + 32-byte account address
COUNTER_BOX_VALUE_LENGTH = 8  # one UInt64
COUNTER_BOX_MBR = (
    BOX_MBR_BASE + (COUNTER_BOX_KEY_LENGTH + COUNTER_BOX_VALUE_LENGTH) * BOX_MBR_PER_BYTE
)


class ReferenceBox(ARC4Contract):
    """
    Per-account counters held in box storage. The first increment for an
    account is funded by a grouped payment covering the box MBR; the contract
    then creates or increments the box on the caller's behalf. Every box an
    app call touches must be declared in the transaction's box reference
    array at call time (the AlgoKit client typically handles this
    automatically).
    """

    def __init__(self) -> None:
        self.account_box_counter = BoxMap(Account, UInt64, key_prefix="counter")

    @arc4.abimethod
    def increment_box_counter(self, pay_mbr: gtxn.PaymentTransaction) -> UInt64:
        """Increment the sender's counter, creating their box on first use.
        The grouped payment must fund the box MBR when the box is first
        created; later increments may pass a zero-amount payment."""
        counter, exists = self.account_box_counter.maybe(Txn.sender)
        if not exists:
            assert pay_mbr.amount >= COUNTER_BOX_MBR, "Payment must cover the box MBR"
            assert (
                pay_mbr.receiver == Global.current_application_address
            ), "Payment must be to the contract"
            counter = UInt64(0)

        new_count = counter + 1
        self.account_box_counter[Txn.sender] = new_count
        return new_count

    @arc4.abimethod(readonly=True)
    def get_box_counter(self) -> UInt64:
        """The sender's counter, or 0 if not yet set."""
        return self.account_box_counter.get(Txn.sender, default=UInt64(0))

    @arc4.abimethod(readonly=True)
    def get_box_counter_for_account(self, account: Account) -> UInt64:
        """The given account's counter, or 0 if not yet set."""
        return self.account_box_counter.get(account, default=UInt64(0))

    @arc4.abimethod(readonly=True)
    def get_box_mbr(self) -> UInt64:
        """The MBR a caller must fund before their first increment — a
        compile-time constant clients can quote without hard-coding it."""
        return UInt64(COUNTER_BOX_MBR)


# example: REFERENCE_BOX_EXAMPLE
