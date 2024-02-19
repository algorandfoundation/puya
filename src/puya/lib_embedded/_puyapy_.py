from puyapy import (
    Bytes,
    OnCompleteAction,
    TransactionType,
    UInt64,
    op,
    subroutine,
)


@subroutine
def ensure_budget(required_budget: UInt64, fee_source: UInt64) -> None:
    # A budget buffer is necessary to deal with an edge case of ensure_budget():
    #   if the current budget is equal to or only slightly higher than the
    #   required budget then it's possible for ensure_budget() to return with a
    #   current budget less than the required budget. The buffer prevents this
    #   from being the case.
    required_budget_with_buffer = required_budget + 10
    while required_budget_with_buffer > op.Global.opcode_budget():
        op.ITxnCreate.begin()
        op.ITxnCreate.set_type_enum(TransactionType.ApplicationCall)
        op.ITxnCreate.set_on_completion(OnCompleteAction.DeleteApplication)
        op.ITxnCreate.set_approval_program(Bytes.from_hex("068101"))
        op.ITxnCreate.set_clear_state_program(Bytes.from_hex("068101"))
        match fee_source:
            case UInt64(0):
                op.ITxnCreate.set_fee(0)
            case UInt64(1):
                op.ITxnCreate.set_fee(op.Global.min_txn_fee)
        op.ITxnCreate.submit()
