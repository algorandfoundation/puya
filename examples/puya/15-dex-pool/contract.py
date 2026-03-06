"""Example 15: DEX Pool

This example demonstrates a constant-product AMM (x*y=k) with inner transactions and wide math.

Features:
- Full constant-product AMM (x*y=k) with 0.3% swap fee
- Asset management (create pool token, opt-in to trading pair)
- BigUInt math for overflow-safe swap computation
- op.bsqrt (BigUInt square root for initial liquidity geometric mean)
- Inner asset transfers (pool token mint, swap output, withdrawals)
- op.mulw / op.divmodw wide math for proportional calculations

Prerequisites: LocalNet

Note: Educational only - not audited for production use.
"""

from algopy import (
    Account,
    ARC4Contract,
    Asset,
    BigUInt,
    Global,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
    subroutine,
)

# Total supply of LP tokens
LP_TOTAL = 10_000_000_000
# Precision scale for fee calculation (basis points)
SCALE = 10_000
# Swap fee: 0.3% = 30 basis points
FEE = 30
# Multiplier after fee
FACTOR = SCALE - FEE


# example: DEX_POOL
class DexPool(ARC4Contract):
    """Constant-product AMM pool for two Algorand Standard Assets.

    Demonstrates BigUInt arithmetic, wide math (op.mulw/op.divmodw),
    inner asset transfers, and liquidity management with a 0.3% swap fee.
    """

    def __init__(self) -> None:
        self.asset_a = Asset()
        self.asset_b = Asset()
        self.pool_token = Asset()
        self.governor = Txn.sender

    @arc4.abimethod(resource_encoding="index")
    def bootstrap(
        self,
        seed: gtxn.PaymentTransaction,
        a_asset: Asset,
        b_asset: Asset,
    ) -> UInt64:
        """Bootstrap the pool: create pool token and opt in to both trading assets.

        Requires a seed payment to fund the contract's min-balance.

        Args:
            seed: Payment transaction to fund the contract's min-balance.
            a_asset: First asset in the trading pair (must have lower ID).
            b_asset: Second asset in the trading pair (must have higher ID).

        Returns:
            The newly created pool token asset ID.
        """
        assert not self.pool_token, "already bootstrapped"
        assert Txn.sender == self.governor, "governor only"
        assert seed.receiver == Global.current_application_address
        assert seed.amount >= 300_000
        assert a_asset.id < b_asset.id, "asset a must be less than asset b"

        self.asset_a = a_asset
        self.asset_b = b_asset
        self.pool_token = self._create_pool_token()
        self._opt_in(self.asset_a)
        self._opt_in(self.asset_b)
        return self.pool_token.id

    @arc4.abimethod(
        default_args={
            "pool_asset": "pool_token",
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="index",
    )
    def add_liquidity(
        self,
        a_xfer: gtxn.AssetTransferTransaction,
        b_xfer: gtxn.AssetTransferTransaction,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """Add liquidity by depositing both assets.

        First deposit uses geometric mean (BigUInt + op.bsqrt).
        Subsequent deposits mint LP tokens proportional to existing reserves.

        Args:
            a_xfer: Asset transfer transaction depositing asset A.
            b_xfer: Asset transfer transaction depositing asset B.
            pool_asset: The pool's LP token asset reference.
            a_asset: Asset A reference.
            b_asset: Asset B reference.
        """
        self._check_bootstrapped()
        assert pool_asset == self.pool_token
        assert a_asset == self.asset_a
        assert b_asset == self.asset_b
        assert a_xfer.sender == Txn.sender
        assert b_xfer.sender == Txn.sender
        assert a_xfer.asset_receiver == Global.current_application_address
        assert b_xfer.asset_receiver == Global.current_application_address
        assert a_xfer.xfer_asset == self.asset_a
        assert b_xfer.xfer_asset == self.asset_b
        assert a_xfer.asset_amount > 0
        assert b_xfer.asset_amount > 0

        to_mint = compute_mint(
            pool_balance=self._pool_balance(),
            a_balance=self._a_balance(),
            b_balance=self._b_balance(),
            a_amount=a_xfer.asset_amount,
            b_amount=b_xfer.asset_amount,
        )
        assert to_mint > 0, "insufficient liquidity minted"
        do_xfer(Txn.sender, self.pool_token, to_mint)

    @arc4.abimethod(
        default_args={
            "pool_asset": "pool_token",
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="index",
    )
    def remove_liquidity(
        self,
        pool_xfer: gtxn.AssetTransferTransaction,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """Remove liquidity by returning pool tokens.

        Proportional amounts of both assets are withdrawn using wide math.

        Args:
            pool_xfer: Asset transfer transaction returning pool tokens.
            pool_asset: The pool's LP token asset reference.
            a_asset: Asset A reference.
            b_asset: Asset B reference.
        """
        self._check_bootstrapped()
        assert pool_asset == self.pool_token
        assert a_asset == self.asset_a
        assert b_asset == self.asset_b
        assert pool_xfer.asset_receiver == Global.current_application_address
        assert pool_xfer.xfer_asset == self.pool_token
        assert pool_xfer.sender == Txn.sender
        assert pool_xfer.asset_amount > 0

        burn_amount = pool_xfer.asset_amount
        pool_balance = self._pool_balance()
        # Circulating LP before this burn (pool_balance already includes burn xfer)
        circulating = LP_TOTAL - pool_balance + burn_amount

        # Proportional withdrawal using wide math (op.mulw/op.divmodw)
        a_out = wide_mul_div(self._a_balance(), burn_amount, circulating)
        b_out = wide_mul_div(self._b_balance(), burn_amount, circulating)

        assert a_out > 0, "insufficient a output"
        assert b_out > 0, "insufficient b output"

        do_xfer(Txn.sender, self.asset_a, a_out)
        do_xfer(Txn.sender, self.asset_b, b_out)

    @arc4.abimethod(
        default_args={
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="index",
    )
    def swap(
        self,
        swap_xfer: gtxn.AssetTransferTransaction,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """Swap one asset for the other using the constant-product formula.

        Deposit asset A to receive asset B, or vice versa.
        A 0.3% fee is deducted from the input.

        Args:
            swap_xfer: Asset transfer transaction depositing the input asset.
            a_asset: Asset A reference.
            b_asset: Asset B reference.
        """
        self._check_bootstrapped()
        assert a_asset == self.asset_a
        assert b_asset == self.asset_b
        assert swap_xfer.asset_amount > 0
        assert swap_xfer.sender == Txn.sender

        in_amount = swap_xfer.asset_amount

        match swap_xfer.xfer_asset:
            case self.asset_a:
                # User sends A, receives B
                in_balance = self._a_balance()
                out_balance = self._b_balance()
                out_asset = self.asset_b
            case self.asset_b:
                # User sends B, receives A
                in_balance = self._b_balance()
                out_balance = self._a_balance()
                out_asset = self.asset_a
            case _:
                assert False, "invalid swap asset"

        # Reserve before swap (balance already includes the incoming transfer)
        in_reserve = in_balance - in_amount
        out_amount = compute_swap(in_amount, in_reserve, out_balance)
        assert out_amount > 0, "insufficient output"

        do_xfer(Txn.sender, out_asset, out_amount)

    # --- Private subroutines ---

    @subroutine
    def _check_bootstrapped(self) -> None:
        assert self.pool_token, "not bootstrapped"

    @subroutine
    def _pool_balance(self) -> UInt64:
        return self.pool_token.balance(Global.current_application_address)

    @subroutine
    def _a_balance(self) -> UInt64:
        return self.asset_a.balance(Global.current_application_address)

    @subroutine
    def _b_balance(self) -> UInt64:
        return self.asset_b.balance(Global.current_application_address)

    @subroutine
    def _create_pool_token(self) -> Asset:
        return (
            itxn.AssetConfig(
                asset_name=b"DPT-" + self.asset_a.unit_name + b"-" + self.asset_b.unit_name,
                unit_name=b"dpt",
                total=LP_TOTAL,
                decimals=3,
                manager=Global.current_application_address,
                reserve=Global.current_application_address,
            )
            .submit()
            .created_asset
        )

    @subroutine
    def _opt_in(self, asset: Asset) -> None:
        do_xfer(Global.current_application_address, asset, UInt64(0))


# --- Module-level subroutines ---


@subroutine
def compute_mint(
    *,
    pool_balance: UInt64,
    a_balance: UInt64,
    b_balance: UInt64,
    a_amount: UInt64,
    b_amount: UInt64,
) -> UInt64:
    """Calculate LP tokens to mint.

    Initial mint uses BigUInt + op.bsqrt for geometric mean.
    Subsequent mints use wide math for proportional calculation.
    """
    is_initial = a_balance == a_amount and b_balance == b_amount
    if is_initial:
        # Geometric mean: sqrt(a * b) using BigUInt to avoid UInt64 overflow
        product = BigUInt(a_amount) * BigUInt(b_amount)
        return op.btoi(op.bsqrt(product).bytes)

    # Subsequent mints: proportional to smaller ratio
    issued = LP_TOTAL - pool_balance
    a_ratio = wide_mul_div(a_amount, issued, a_balance - a_amount)
    b_ratio = wide_mul_div(b_amount, issued, b_balance - b_amount)
    if a_ratio < b_ratio:
        return a_ratio
    else:
        return b_ratio


@subroutine
def compute_swap(in_amount: UInt64, in_reserve: UInt64, out_reserve: UInt64) -> UInt64:
    """Constant-product swap with 0.3% fee using BigUInt arithmetic.

    Formula: out = out_reserve * in_amount * FACTOR / (in_reserve * SCALE + in_amount * FACTOR)
    Uses BigUInt for overflow-safe triple multiplication.
    """
    numerator = BigUInt(out_reserve) * BigUInt(in_amount) * BigUInt(FACTOR)
    denominator = BigUInt(in_reserve) * BigUInt(SCALE) + BigUInt(in_amount) * BigUInt(FACTOR)
    return op.btoi((numerator // denominator).bytes)


@subroutine
def wide_mul_div(a: UInt64, b: UInt64, c: UInt64) -> UInt64:
    """Compute (a * b) / c using 128-bit wide math (op.mulw + op.divmodw).

    Avoids UInt64 overflow on the intermediate product a * b.
    """
    hi, lo = op.mulw(a, b)
    q_hi, q_lo, rem_hi, rem_lo = op.divmodw(hi, lo, UInt64(0), c)
    assert not q_hi, "result overflow"
    return q_lo


@subroutine
def do_xfer(receiver: Account, asset: Asset, amount: UInt64) -> None:
    """Execute an inner asset transfer."""
    itxn.AssetTransfer(
        xfer_asset=asset,
        asset_amount=amount,
        asset_receiver=receiver,
    ).submit()


# example: DEX_POOL
