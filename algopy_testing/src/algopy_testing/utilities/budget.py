from __future__ import annotations

from algopy_testing import UInt64


class OpUpFeeSource(UInt64):
    """Defines the source of fees for the OpUp utility."""

    GroupCredit: OpUpFeeSource
    AppAccount: OpUpFeeSource
    Any: OpUpFeeSource


OpUpFeeSource.GroupCredit = OpUpFeeSource(0)
OpUpFeeSource.AppAccount = OpUpFeeSource(1)
OpUpFeeSource.Any = OpUpFeeSource(2)


def ensure_budget(
    required_budget: UInt64 | int,  # noqa: ARG001
    fee_source: OpUpFeeSource = OpUpFeeSource.GroupCredit,  # noqa: ARG001
) -> None:
    pass
