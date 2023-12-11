from enum import Enum

from puyapy import UInt64

class OpUpFeeSource(Enum):
    """An Enum object that defines the source for fees for the OpUp utility."""

    #: Only the excess fee (credit) on the outer group should be used (set inner_tx.fee=0)
    GroupCredit = 0
    #: The app's account will cover all fees (set inner_tx.fee=Global.min_tx_fee())
    AppAccount = 1
    #: First the excess will be used, remaining fees will be taken from the app account
    Any = 2

def ensure_budget(
    required_budget: UInt64 | int, fee_source: OpUpFeeSource = OpUpFeeSource.Any
) -> None:
    """
    Ensure the available op code budget is greater than or equal to required_budget
    """
