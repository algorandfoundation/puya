from puyapy import UInt64

class OpUpFeeSource(UInt64):
    """Defines the source of fees for the OpUp utility."""

    GroupCredit: OpUpFeeSource = ...
    """Only the excess fee (credit) on the outer group should be used (set inner_tx.fee=0)"""
    AppAccount: OpUpFeeSource = ...
    """The app's account will cover all fees (set inner_tx.fee=Global.min_tx_fee())"""
    Any: OpUpFeeSource = ...
    """First the excess will be used, remaining fees will be taken from the app account"""

def ensure_budget(
    required_budget: UInt64 | int, fee_source: OpUpFeeSource = OpUpFeeSource.Any
) -> None:
    """Ensure the available op code budget is greater than or equal to required_budget"""
