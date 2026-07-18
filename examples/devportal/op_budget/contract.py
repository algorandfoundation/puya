from algopy import (
    ARC4Contract,
    Bytes,
    OpUpFeeSource,
    UInt64,
    arc4,
    ensure_budget,
    op,
    urange,
)


class OpBudget(ARC4Contract):
    """
    Demonstrates `ensure_budget`: the standard way to extend the AVM opcode
    budget for operations that exceed the default 700-op-per-txn cap (besides
    group pooling).

    Under the hood `ensure_budget` issues inner application calls to a no-op
    `OpUp` app, each of which carries its own 700-op budget that this txn
    can consume. The `OpUpFeeSource` argument controls how the inner txn fees
    are paid.
    """

    # example: ENSURE_BUDGET_BASIC
    @arc4.abimethod
    def many_hashes(self, seed: Bytes, rounds: UInt64) -> Bytes:
        """
        Each `op.sha256` costs 35 ops, so chaining many of them consumes
        budget quickly. `ensure_budget(required)` requests enough
        additional budget to cover `required` ops.

        The argument is the *total* op budget you want available, not the
        delta from the current budget.
        """
        # ~40 ops per iteration (sha256 costs 35, plus loop overhead),
        # plus a 100-op allowance for method routing and returning
        ensure_budget(rounds * 40 + 100)

        digest = seed
        for _i in urange(rounds):
            digest = op.sha256(digest)
        return digest

    # example: ENSURE_BUDGET_BASIC

    # example: ENSURE_BUDGET_FEE_SOURCE
    @arc4.abimethod
    def many_hashes_group_credit(self, seed: Bytes, rounds: UInt64) -> Bytes:
        """
        `OpUpFeeSource.GroupCredit` (the default): the inner OpUp call sets
        `fee=0` and relies on the outer transaction group having paid extra
        fees in advance. Callers must include enough excess fee on some other
        txn in the group to cover the inner OpUp calls. Cheapest when the
        caller is already paying group fees anyway.
        """
        ensure_budget(rounds * 40 + 100, fee_source=OpUpFeeSource.GroupCredit)
        digest = seed
        for _i in urange(rounds):
            digest = op.sha256(digest)
        return digest

    @arc4.abimethod
    def many_hashes_app_pays(self, seed: Bytes, rounds: UInt64) -> Bytes:
        """
        `OpUpFeeSource.AppAccount`: the application's own account pays for
        the inner OpUp calls (their `fee` is set to `Global.min_txn_fee`).
        Use this when the caller cannot or should not over-pay the group
        fees. Requires the app account to hold enough algos.
        """
        ensure_budget(rounds * 40 + 100, fee_source=OpUpFeeSource.AppAccount)
        digest = seed
        for _i in urange(rounds):
            digest = op.sha256(digest)
        return digest

    @arc4.abimethod
    def many_hashes_any(self, seed: Bytes, rounds: UInt64) -> Bytes:
        """
        `OpUpFeeSource.Any`: spend the group's excess fee credit first, then
        fall back to the app account if more is needed. Most flexible; the
        right default for contracts that want to be "polite" about fees.
        """
        ensure_budget(rounds * 40 + 100, fee_source=OpUpFeeSource.Any)
        digest = seed
        for _i in urange(rounds):
            digest = op.sha256(digest)
        return digest

    # example: ENSURE_BUDGET_FEE_SOURCE
