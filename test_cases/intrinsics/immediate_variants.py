from puyapy import (
    Bytes,
    Contract,
    OnCompleteAction,
    TransactionType,
    UInt64,
)
from puyapy.op import (
    CreateInnerTransaction,
    InnerTransaction,
    InnerTransactionGroup,
    Transaction,
    TransactionGroup,
)


class ImmediateVariants(Contract):
    def approval_program(self) -> bool:
        num_app_args = Transaction.num_app_args
        assert TransactionGroup.num_app_args(0) == num_app_args
        assert TransactionGroup.num_app_args(UInt64(0)) == num_app_args
        first_arg = Transaction.application_args(0)
        assert Transaction.application_args(UInt64(0)) == first_arg
        assert TransactionGroup.application_args(0, 0) == first_arg
        assert TransactionGroup.application_args(0, UInt64(0)) == first_arg
        assert TransactionGroup.application_args(UInt64(0), 0) == first_arg
        assert TransactionGroup.application_args(UInt64(0), UInt64(0)) == first_arg

        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.ApplicationCall)
        CreateInnerTransaction.set_on_completion(OnCompleteAction.DeleteApplication)
        CreateInnerTransaction.set_approval_program(Bytes.from_hex("068101"))
        CreateInnerTransaction.set_clear_state_program(Bytes.from_hex("068101"))
        CreateInnerTransaction.set_fee(0)  # cover fee with outer txn
        CreateInnerTransaction.set_fee(UInt64(0))  # cover fee with outer txn
        CreateInnerTransaction.set_application_args(first_arg)
        second_arg = first_arg + b"2"
        CreateInnerTransaction.set_application_args(second_arg)
        CreateInnerTransaction.submit()

        assert InnerTransaction.num_app_args == 2
        assert InnerTransaction.application_args(0) == first_arg
        assert InnerTransaction.application_args(UInt64(1)) == second_arg

        assert InnerTransactionGroup.num_app_args(0) == 2
        assert InnerTransactionGroup.application_args(0, UInt64(0)) == first_arg
        assert InnerTransactionGroup.application_args(0, UInt64(1)) == second_arg
        assert InnerTransactionGroup.application_args(0, 0) == first_arg
        assert InnerTransactionGroup.application_args(0, 1) == second_arg

        return True

    def clear_state_program(self) -> bool:
        return True
