# WARNING: This code is provided for example only. Do NOT deploy to mainnet.

from algopy import (
    Account,
    ARC4Contract,
    Asset,
    Global,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
    subroutine,
)

# Total supply of the pool tokens
TOTAL_SUPPLY = 10_000_000_000
# scale helps with precision when doing computation for
# the number of tokens to transfer
SCALE = 1000
# Fee for swaps, 5 represents 0.5% ((fee / scale)*100)
FEE = 5
FACTOR = SCALE - FEE


class ConstantProductAMM(ARC4Contract):
    def __init__(self) -> None:
        # init runs whenever the txn's app ID is zero, and runs first
        # so if we have multiple create methods, this can contain common code.

        # The asset id of asset A
        self.asset_a = Asset()
        # The asset id of asset B
        self.asset_b = Asset()
        # The current governor of this contract, allowed to do admin type actions
        self.governor = Txn.sender
        # The asset id of the Pool Token, used to track share of pool the holder may recover
        self.pool_token = Asset()
        # The ratio between assets (A*Scale/B)
        self.ratio = UInt64(0)

    @arc4.abimethod()
    def set_governor(self, new_governor: Account) -> None:
        """sets the governor of the contract, may only be called by the current governor"""
        self._check_is_governor()
        self.governor = new_governor

    @arc4.abimethod(resource_encoding="foreign_index")
    def bootstrap(self, seed: gtxn.PaymentTransaction, a_asset: Asset, b_asset: Asset) -> UInt64:
        """bootstraps the contract by opting into the assets and creating the pool token.

        Note this method will fail if it is attempted more than once on the same contract
        since the assets and pool token application state values are marked as static and
        cannot be overridden.

        Args:
            seed: Initial Payment transaction to the app account so it can opt in to assets
                and create pool token.
            a_asset: One of the two assets this pool should allow swapping between.
            b_asset: The other of the two assets this pool should allow swapping between.

        Returns:
            The asset id of the pool token created.
        """
        assert not self.pool_token, "application has already been bootstrapped"
        self._check_is_governor()
        assert Global.group_size == 2, "group size not 2"
        assert seed.receiver == Global.current_application_address, "receiver not app address"

        assert seed.amount >= 300_000, "amount minimum not met"  # 0.3 Algos
        assert a_asset.id < b_asset.id, "asset a must be less than asset b"
        self.asset_a = a_asset
        self.asset_b = b_asset
        self.pool_token = self._create_pool_token()

        self._do_opt_in(self.asset_a)
        self._do_opt_in(self.asset_b)
        return self.pool_token.id

    @arc4.abimethod(
        default_args={
            "pool_asset": "pool_token",
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="foreign_index",
    )
    def mint(
        self,
        a_xfer: gtxn.AssetTransferTransaction,
        b_xfer: gtxn.AssetTransferTransaction,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """mint pool tokens given some amount of asset A and asset B.

        Given some amount of Asset A and Asset B in the transfers, mint some number of pool
        tokens commensurate with the pools current balance and circulating supply of
        pool tokens.

        Args:
            a_xfer: Asset Transfer Transaction of asset A as a deposit to the pool in
                exchange for pool tokens.
            b_xfer: Asset Transfer Transaction of asset B as a deposit to the pool in
                exchange for pool tokens.
            pool_asset: The asset ID of the pool token so that we may distribute it.
            a_asset: The asset ID of the Asset A so that we may inspect our balance.
            b_asset: The asset ID of the Asset B so that we may inspect our balance.
        """
        self._check_bootstrapped()

        # well-formed mint
        assert pool_asset == self.pool_token, "asset pool incorrect"
        assert a_asset == self.asset_a, "asset a incorrect"
        assert b_asset == self.asset_b, "asset b incorrect"
        assert a_xfer.sender == Txn.sender, "sender invalid"
        assert b_xfer.sender == Txn.sender, "sender invalid"

        # valid asset a xfer
        assert (
            a_xfer.asset_receiver == Global.current_application_address
        ), "receiver not app address"
        assert a_xfer.xfer_asset == self.asset_a, "asset a incorrect"
        assert a_xfer.asset_amount > 0, "amount minimum not met"

        # valid asset b xfer
        assert (
            b_xfer.asset_receiver == Global.current_application_address
        ), "receiver not app address"
        assert b_xfer.xfer_asset == self.asset_b, "asset b incorrect"
        assert b_xfer.asset_amount > 0, "amount minimum not met"

        to_mint = tokens_to_mint(
            pool_balance=self._current_pool_balance(),
            a_balance=self._current_a_balance(),
            b_balance=self._current_b_balance(),
            a_amount=a_xfer.asset_amount,
            b_amount=b_xfer.asset_amount,
        )
        assert to_mint > 0, "send amount too low"

        # mint tokens
        do_asset_transfer(receiver=Txn.sender, asset=self.pool_token, amount=to_mint)
        self._update_ratio()

    @arc4.abimethod(
        default_args={
            "pool_asset": "pool_token",
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="foreign_index",
    )
    def burn(
        self,
        pool_xfer: gtxn.AssetTransferTransaction,
        pool_asset: Asset,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """burn pool tokens to get back some amount of asset A and asset B

        Args:
            pool_xfer: Asset Transfer Transaction of the pool token for the amount the
                sender wishes to redeem
            pool_asset: Asset ID of the pool token so we may inspect balance.
            a_asset: Asset ID of Asset A so we may inspect balance and distribute it
            b_asset: Asset ID of Asset B so we may inspect balance and distribute it
        """
        self._check_bootstrapped()

        assert pool_asset == self.pool_token, "asset pool incorrect"
        assert a_asset == self.asset_a, "asset a incorrect"
        assert b_asset == self.asset_b, "asset b incorrect"

        assert (
            pool_xfer.asset_receiver == Global.current_application_address
        ), "receiver not app address"
        assert pool_xfer.asset_amount > 0, "amount minimum not met"
        assert pool_xfer.xfer_asset == self.pool_token, "asset pool incorrect"
        assert pool_xfer.sender == Txn.sender, "sender invalid"

        # Get the total number of tokens issued
        # !important: this happens prior to receiving the current axfer of pool tokens
        pool_balance = self._current_pool_balance()
        a_amt = tokens_to_burn(
            pool_balance=pool_balance,
            supply=self._current_a_balance(),
            amount=pool_xfer.asset_amount,
        )
        b_amt = tokens_to_burn(
            pool_balance=pool_balance,
            supply=self._current_b_balance(),
            amount=pool_xfer.asset_amount,
        )

        # Send back commensurate amt of a
        do_asset_transfer(receiver=Txn.sender, asset=self.asset_a, amount=a_amt)

        # Send back commensurate amt of b
        do_asset_transfer(receiver=Txn.sender, asset=self.asset_b, amount=b_amt)
        self._update_ratio()

    @arc4.abimethod(
        default_args={
            "a_asset": "asset_a",
            "b_asset": "asset_b",
        },
        resource_encoding="foreign_index",
    )
    def swap(
        self,
        swap_xfer: gtxn.AssetTransferTransaction,
        a_asset: Asset,
        b_asset: Asset,
    ) -> None:
        """Swap some amount of either asset A or asset B for the other

        Args:
            swap_xfer: Asset Transfer Transaction of either Asset A or Asset B
            a_asset: Asset ID of asset A so we may inspect balance and possibly transfer it
            b_asset: Asset ID of asset B so we may inspect balance and possibly transfer it
        """
        self._check_bootstrapped()

        assert a_asset == self.asset_a, "asset a incorrect"
        assert b_asset == self.asset_b, "asset b incorrect"

        assert swap_xfer.asset_amount > 0, "amount minimum not met"
        assert swap_xfer.sender == Txn.sender, "sender invalid"

        match swap_xfer.xfer_asset:
            case self.asset_a:
                in_supply = self._current_b_balance()
                out_supply = self._current_a_balance()
                out_asset = self.asset_a
            case self.asset_b:
                in_supply = self._current_a_balance()
                out_supply = self._current_b_balance()
                out_asset = self.asset_b
            case _:
                assert False, "asset id incorrect"

        to_swap = tokens_to_swap(
            in_amount=swap_xfer.asset_amount, in_supply=in_supply, out_supply=out_supply
        )
        assert to_swap > 0, "send amount too low"

        do_asset_transfer(receiver=Txn.sender, asset=out_asset, amount=to_swap)
        self._update_ratio()

    @subroutine
    def _check_bootstrapped(self) -> None:
        assert self.pool_token, "bootstrap method needs to be called first"

    @subroutine
    def _update_ratio(self) -> None:
        a_balance = self._current_a_balance()
        b_balance = self._current_b_balance()

        self.ratio = a_balance * SCALE // b_balance

    @subroutine
    def _check_is_governor(self) -> None:
        assert (
            Txn.sender == self.governor
        ), "Only the account set in global_state.governor may call this method"

    @subroutine
    def _create_pool_token(self) -> Asset:
        return (
            itxn.AssetConfig(
                asset_name=b"DPT-" + self.asset_a.unit_name + b"-" + self.asset_b.unit_name,
                unit_name=b"dbt",
                total=TOTAL_SUPPLY,
                decimals=3,
                manager=Global.current_application_address,
                reserve=Global.current_application_address,
            )
            .submit()
            .created_asset
        )

    @subroutine
    def _do_opt_in(self, asset: Asset) -> None:
        do_asset_transfer(
            receiver=Global.current_application_address,
            asset=asset,
            amount=UInt64(0),
        )

    @subroutine
    def _current_pool_balance(self) -> UInt64:
        return self.pool_token.balance(Global.current_application_address)

    @subroutine
    def _current_a_balance(self) -> UInt64:
        return self.asset_a.balance(Global.current_application_address)

    @subroutine
    def _current_b_balance(self) -> UInt64:
        return self.asset_b.balance(Global.current_application_address)


##############
# Mathy methods
##############

# Notes:
#   1) During arithmetic operations, depending on the inputs, these methods may overflow
#   the max uint64 value. This will cause the program to immediately terminate.
#
#   Care should be taken to fully understand the limitations of these functions and if
#   required should be swapped out for the appropriate byte math operations.
#
#   2) When doing division, any remainder is truncated from the result.
#
#   Care should be taken  to ensure that _when_ the truncation happens,
#   it does so in favor of the contract. This is a subtle security issue that,
#   if mishandled, could cause the balance of the contract to be drained.


@subroutine
def tokens_to_mint(
    *,
    pool_balance: UInt64,
    a_balance: UInt64,
    b_balance: UInt64,
    a_amount: UInt64,
    b_amount: UInt64,
) -> UInt64:
    is_initial_mint = a_balance == a_amount and b_balance == b_amount
    if is_initial_mint:
        return op.sqrt(a_amount * b_amount) - SCALE
    issued = TOTAL_SUPPLY - pool_balance
    a_ratio = SCALE * a_amount // (a_balance - a_amount)
    b_ratio = SCALE * b_amount // (b_balance - b_amount)
    if a_ratio < b_ratio:
        return a_ratio * issued // SCALE
    else:
        return b_ratio * issued // SCALE


@subroutine
def tokens_to_burn(*, pool_balance: UInt64, supply: UInt64, amount: UInt64) -> UInt64:
    issued = TOTAL_SUPPLY - pool_balance - amount
    return supply * amount // issued


@subroutine
def tokens_to_swap(*, in_amount: UInt64, in_supply: UInt64, out_supply: UInt64) -> UInt64:
    in_total = SCALE * (in_supply - in_amount) + (in_amount * FACTOR)
    out_total = in_amount * FACTOR * out_supply
    return out_total // in_total


@subroutine
def do_asset_transfer(*, receiver: Account, asset: Asset, amount: UInt64) -> None:
    itxn.AssetTransfer(
        xfer_asset=asset,
        asset_amount=amount,
        asset_receiver=receiver,
    ).submit()
