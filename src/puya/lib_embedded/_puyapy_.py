from puyapy import (
    Bytes,
    CreateInnerTransaction,
    Global,
    OnCompleteAction,
    TransactionType,
    UInt64,
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
    while required_budget_with_buffer > Global.opcode_budget():
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.ApplicationCall)
        CreateInnerTransaction.set_on_completion(OnCompleteAction.DeleteApplication)
        CreateInnerTransaction.set_approval_program(Bytes.from_hex("068101"))
        CreateInnerTransaction.set_clear_state_program(Bytes.from_hex("068101"))
        match fee_source:
            case UInt64(0):
                CreateInnerTransaction.set_fee(0)
            case UInt64(1):
                CreateInnerTransaction.set_fee(Global.min_txn_fee())
        CreateInnerTransaction.submit()
