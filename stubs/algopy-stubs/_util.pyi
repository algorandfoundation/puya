from algopy import Bytes, BytesBacked, String, UInt64

class OpUpFeeSource(UInt64):
    """Defines the source of fees for the OpUp utility."""

    GroupCredit: OpUpFeeSource = ...
    """Only the excess fee (credit) on the outer group should be used (set inner_tx.fee=0)"""
    AppAccount: OpUpFeeSource = ...
    """The app's account will cover all fees (set inner_tx.fee=Global.min_tx_fee())"""
    Any: OpUpFeeSource = ...
    """First the excess will be used, remaining fees will be taken from the app account"""

def ensure_budget(
    required_budget: UInt64 | int, fee_source: OpUpFeeSource = OpUpFeeSource.GroupCredit
) -> None:
    """Ensure the available op code budget is greater than or equal to required_budget"""

def log(
    *args: UInt64 | Bytes | BytesBacked | str | bytes | int, sep: String | str | Bytes | bytes = ""
) -> None:
    """Concatenates and logs supplied args as a single bytes value.

    UInt64 args are converted to bytes and each argument is separated by `sep`.
    Literal `str` values will be encoded as UTF8.
    """
