from algopy import ARC4Contract, UInt64, arc4, logged_assert, logged_err


class LoggedErrors(ARC4Contract):
    """
    Demonstrates `logged_assert` and `logged_err`: ARC-65-compliant error
    helpers that log a structured `ERR:{error_code}:{error_message}`
    string before failing the transaction.

    ARC-65 suggests error codes be camel case and alphanumeric (the compiler
    emits a warning when a code does not follow this format).
    Furthermore, code and message may not contain ':', as this character
    is the domain separator for ARC-65 (the compiler will error if code
    or message contain ':').

    Compared to a plain `assert ..., "msg"` this:
      * Always logs the error, so failed transactions in algod carry it
        in their response.
      * Uses an explicit short code clients can match against.

    The trade-off is bytecode size: every distinct code + message becomes a
    byte string in the program, so keep both as short as possible.
    """

    def __init__(self) -> None:
        self.balance = UInt64(0)

    @arc4.abimethod
    def deposit(self, amount: UInt64) -> UInt64:
        self.balance += amount
        return self.balance

    # example: LOGGED_ASSERT
    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        # `logged_assert(condition, error_code, error_message=..., prefix=...)`
        # logs `ERR:amountError01:amount must be positive` and aborts when the
        # condition is false. `desc=` additionally sets a plain description in
        # the ARC-56 source info — the human-readable error typed clients
        # surface — without changing the logged output.
        logged_assert(
            amount > 0,
            "amountError01",
            "amount must be positive",
            desc="Withdrawal amount must be greater than zero",
        )
        logged_assert(
            amount <= self.balance,
            "amountError02",
            "insufficient balance",
        )

        self.balance -= amount
        return self.balance

    # example: LOGGED_ASSERT

    # example: LOGGED_ERR
    @arc4.abimethod
    def reject(self, code: UInt64) -> UInt64:
        # `logged_err` is the unconditional version of `logged_assert`; it is
        # equivalent to `logged_assert(False, ...)`. Useful inside branches
        # where the failure decision has already been made.
        if code == 0:
            logged_err("codeRange00", "code zero is reserved")
        if code > 100:
            logged_err("codeRange01", "code out of range")
        return code

    # example: LOGGED_ERR
