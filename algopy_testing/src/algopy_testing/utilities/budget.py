from __future__ import annotations

from algopy_testing import UInt64
from algopy_testing.constants import DEFAULT_TEST_CTX_OPCODE_BUDGET


class OpUpFeeSource(UInt64):
    """Defines the source of fees for the OpUp utility."""

    GroupCredit: OpUpFeeSource
    AppAccount: OpUpFeeSource
    Any: OpUpFeeSource


OpUpFeeSource.GroupCredit = OpUpFeeSource(0)
OpUpFeeSource.AppAccount = OpUpFeeSource(1)
OpUpFeeSource.Any = OpUpFeeSource(2)


def ensure_budget(
    required_budget: UInt64 | int,
    fee_source: OpUpFeeSource = OpUpFeeSource.GroupCredit,  # noqa: ARG001
) -> None:
    from algopy_testing import get_test_context

    ctx = get_test_context()
    app_call_budget = DEFAULT_TEST_CTX_OPCODE_BUDGET
    if not ctx:
        raise RuntimeError("No test context found")

    if ctx._active_contract and ctx._active_contract in ctx._op_code_budgets:
        app_call_budget = ctx._op_code_budgets[ctx._active_contract]

    if app_call_budget < required_budget:
        raise RuntimeError(
            f"Op code budget for {ctx._active_contract} is less than {required_budget}"
        )
