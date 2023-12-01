# WARNING: This code is provided for example only. Do NOT deploy to mainnet.

from algopy import (
    Address,
    ARC4Contract,
    AssetHoldingGet,
    AssetParamsGet,
    Bytes,
    CreateInnerTransaction,
    Global,
    InnerTransaction,
    Transaction,
    TransactionType,
    UInt64,
    arc4,
    sqrt,
    subroutine,
)
from algopy.arc4 import AssetTransferTransaction, PaymentTransaction

# Total supply of the pool tokens
TOTAL_SUPPLY = 10_000_000_000
# scale helps with precision when doing computation for
# the number of tokens to transfer
SCALE = 1000
# Fee for swaps, 5 represents 0.5% ((fee / scale)*100)
FEE = 5
FACTOR = SCALE - FEE


class ConstantProductionAMM(ARC4Contract):
    def __init__(self) -> None:
        # init runs whenever the txn's app ID is zero, and runs first
        # so if we have multiple create methods, this can contain common code.

        # The asset id of asset A
        self.asset_a = UInt64(0)
        # The asset id of asset B
        self.asset_b = UInt64(0)
        # The asset id of the Pool Token, used to track share of pool the holder may recover
        self.pool_token = UInt64(0)
        # # The ratio between assets (A*Scale/B)
        # self.ratio: UInt64 | None = None
        # The current governor of this contract, allowed to do admin type actions
        self.governor = Transaction.sender()

    @arc4.abimethod(create=True)
    def create(self) -> None:
        """Allow creates"""

    @arc4.abimethod()
    def set_governor(self, new_governor: arc4.Account) -> None:
        self._check_is_governor()
        self.governor = new_governor.address

    @arc4.abimethod()
    def bootstrap(self, seed: PaymentTransaction, asset_a: UInt64, asset_b: UInt64) -> UInt64:
        """bootstraps the contract by opting into the assets and creating the pool token.

        This method will fail if it is attempted more than once on the same contract.

        Args:
            seed: Initial Payment transaction to the app account,
                  so it can opt in to assets and create pool token.
            asset_a: One of the two assets this pool should allow swapping between.
                     Must be in the foreign assets array
            asset_b: The other of the two assets this pool should allow swapping between.
                     Must be in the foreign assets array

        Returns:
            The asset id of the pool token created.
        """
        assert self.pool_token == 0, "application has already been bootstrapped"
        self._check_is_governor()
        assert Global.group_size() == 2, "group size not 2"
        assert seed.receiver == Global.current_application_address(), "receiver not app address"

        assert seed.amount >= 300_000, "amount minimum not met"  # 0.3 Algos
        assert asset_a < asset_b, "asset a must be less than asset b"
        self.asset_a = asset_a
        self.asset_b = asset_b
        self._create_pool_token()

        self._do_opt_in(self.asset_a)
        self._do_opt_in(self.asset_b)
        return self.pool_token

    @arc4.abimethod()
    def mint(
        self,
        a_xfer: AssetTransferTransaction,
        b_xfer: AssetTransferTransaction,
    ) -> None:
        """mint pool tokens given some amount of asset A and asset B.

        Given some amount of Asset A and Asset B in the transfers, mint some number of pool
        tokens commensurate with the pools current balance and circulating supply of
        pool tokens.

        NOTE: asset_a, asset_b and pool_token must be in the foreign assets array

        Args:
            a_xfer: Asset Transfer Transaction of asset A as a deposit to the pool in
                exchange for pool tokens.
            b_xfer: Asset Transfer Transaction of asset B as a deposit to the pool in
                exchange for pool tokens.
        """
        self._check_bootstrapped()

        # well-formed mint
        assert a_xfer.sender == Transaction.sender(), "sender invalid"
        assert b_xfer.sender == Transaction.sender(), "sender invalid"

        # valid asset a xfer
        assert (
            a_xfer.asset_receiver == Global.current_application_address()
        ), "receiver not app address"
        assert a_xfer.xfer_asset == self.asset_a, "asset a incorrect"
        assert a_xfer.asset_amount > 0, "amount minimum not met"

        # valid asset b xfer
        assert (
            b_xfer.asset_receiver == Global.current_application_address()
        ), "receiver not app address"
        assert b_xfer.xfer_asset == self.asset_a, "asset b incorrect"
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
        do_asset_transfer(receiver=Transaction.sender(), asset_id=self.pool_token, amount=to_mint)
        self._update_ratio()

    @arc4.abimethod()
    def burn(self, pool_xfer: AssetTransferTransaction) -> None:
        """burn pool tokens to get back some amount of asset A and asset B

        NOTE: asset_a, asset_b and pool_token must be in the foreign assets array

        Args:
            pool_xfer: Asset Transfer Transaction of the pool token for the amount the
                sender wishes to redeem
        """
        self._check_bootstrapped()

        assert (
            pool_xfer.asset_receiver == Global.current_application_address()
        ), "receiver not app address"
        assert pool_xfer.asset_amount > 0, "amount minimum not met"
        assert pool_xfer.xfer_asset == self.pool_token, "asset pool incorrect"
        assert pool_xfer.sender == Transaction.sender(), "sender invalid"

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
        do_asset_transfer(receiver=Transaction.sender(), asset_id=self.asset_a, amount=a_amt)

        # Send back commensurate amt of b
        do_asset_transfer(receiver=Transaction.sender(), asset_id=self.asset_b, amount=b_amt)
        self._update_ratio()

    @arc4.abimethod()
    def swap(self, swap_xfer: AssetTransferTransaction) -> None:
        """Swap some amount of either asset A or asset B for the other

        NOTE: asset_a and asset_b must be in the foreign assets array

        Args:
            swap_xfer: Asset Transfer Transaction of either Asset A or Asset B
        """
        self._check_bootstrapped()

        assert swap_xfer.asset_amount > 0, "amount minimum not met"
        assert swap_xfer.sender == Transaction.sender(), "sender invalid"

        match swap_xfer.xfer_asset:
            case self.asset_a:
                in_supply = self._current_b_balance()
                out_supply = self._current_a_balance()
                out_id = self.asset_a
            case self.asset_b:
                in_supply = self._current_a_balance()
                out_supply = self._current_b_balance()
                out_id = self.asset_b
            case _:
                assert False, "asset id incorrect"

        to_swap = tokens_to_swap(
            in_amount=swap_xfer.asset_amount, in_supply=in_supply, out_supply=out_supply
        )
        assert to_swap > 0, "send amount too low"

        do_asset_transfer(receiver=Transaction.sender(), asset_id=out_id, amount=to_swap)
        self._update_ratio()

    @subroutine
    def _check_bootstrapped(self) -> None:
        assert self.pool_token != 0, "bootstrap method needs to be called first"

    @subroutine
    def _update_ratio(self) -> None:
        a_balance = self._current_a_balance()
        b_balance = self._current_b_balance()

        self.ratio = a_balance * SCALE // b_balance

    @subroutine
    def _check_is_governor(self) -> None:
        assert (
            Transaction.sender() == self.governor
        ), "Only the account set in global_state.governor may call this method"

    @subroutine
    def _create_pool_token(self) -> None:
        unit_a, unit_a_exists = AssetParamsGet.asset_unit_name(self.asset_a)
        assert unit_a_exists

        unit_b, unit_b_exists = AssetParamsGet.asset_unit_name(self.asset_b)
        assert unit_b_exists

        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetConfig)
        CreateInnerTransaction.set_config_asset_name(
            Bytes(b"DPT-") + unit_a + Bytes(b"-") + unit_b
        )
        CreateInnerTransaction.set_config_asset_unit_name(b"dpt")
        CreateInnerTransaction.set_config_asset_total(TOTAL_SUPPLY)
        CreateInnerTransaction.set_config_asset_decimals(3)
        CreateInnerTransaction.set_config_asset_manager(Global.current_application_address())
        CreateInnerTransaction.set_config_asset_reserve(Global.current_application_address())
        CreateInnerTransaction.set_fee(0)
        CreateInnerTransaction.submit()

        self.pool_token = InnerTransaction.created_asset_id()

    @subroutine
    def _do_opt_in(self, asset_id: UInt64) -> None:
        do_asset_transfer(
            receiver=Global.current_application_address(),
            asset_id=asset_id,
            amount=UInt64(0),
        )

    @subroutine
    def _current_pool_balance(self) -> UInt64:
        balance, has_balance = AssetHoldingGet.asset_balance(
            Global.current_application_address(),
            self.pool_token,
        )
        assert has_balance
        return balance

    @subroutine
    def _current_a_balance(self) -> UInt64:
        balance, has_balance = AssetHoldingGet.asset_balance(
            Global.current_application_address(),
            self.asset_a,
        )
        assert has_balance
        return balance

    @subroutine
    def _current_b_balance(self) -> UInt64:
        balance, has_balance = AssetHoldingGet.asset_balance(
            Global.current_application_address(),
            self.asset_b,
        )
        assert has_balance
        return balance


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
        return sqrt(a_amount * b_amount) - SCALE
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
def do_asset_transfer(*, receiver: Address, asset_id: UInt64, amount: UInt64) -> None:
    CreateInnerTransaction.begin()
    CreateInnerTransaction.set_type_enum(TransactionType.AssetTransfer)
    CreateInnerTransaction.set_xfer_asset(asset_id)
    CreateInnerTransaction.set_asset_amount(amount)
    CreateInnerTransaction.set_asset_receiver(receiver)
    CreateInnerTransaction.set_fee(0)
    CreateInnerTransaction.submit()
