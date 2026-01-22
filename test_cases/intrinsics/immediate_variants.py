from algopy import (
    Bytes,
    Contract,
    OnCompleteAction,
    TransactionType,
    UInt64,
)
from algopy.op import (
    GITxn,
    GTxn,
    ITxn,
    ITxnCreate,
    Txn,
)


class ImmediateVariants(Contract):
    def approval_program(self) -> bool:
        num_app_args = Txn.num_app_args
        assert GTxn.num_app_args(0) == num_app_args
        assert GTxn.num_app_args(UInt64(0)) == num_app_args
        first_arg = Txn.application_args(0)
        assert Txn.application_args(UInt64(0)) == first_arg
        assert GTxn.application_args(0, 0) == first_arg
        assert GTxn.application_args(0, UInt64(0)) == first_arg
        assert GTxn.application_args(UInt64(0), 0) == first_arg
        assert GTxn.application_args(UInt64(0), UInt64(0)) == first_arg

        ITxnCreate.begin()
        ITxnCreate.set_type_enum(TransactionType.ApplicationCall)
        ITxnCreate.set_on_completion(OnCompleteAction.DeleteApplication)
        ITxnCreate.set_approval_program(Bytes.from_hex("068101"))
        ITxnCreate.set_clear_state_program(Bytes.from_hex("068101"))
        ITxnCreate.set_fee(0)  # cover fee with outer txn
        ITxnCreate.set_fee(UInt64(0))  # cover fee with outer txn
        ITxnCreate.set_application_args(first_arg)
        second_arg = first_arg + b"2"
        ITxnCreate.set_application_args(second_arg)
        ITxnCreate.submit()

        assert ITxn.num_app_args() == 2
        assert ITxn.application_args(0) == first_arg
        assert ITxn.application_args(UInt64(1)) == second_arg

        assert GITxn.num_app_args(0) == 2
        assert GITxn.application_args(0, UInt64(0)) == first_arg
        assert GITxn.application_args(0, UInt64(1)) == second_arg
        assert GITxn.application_args(0, 0) == first_arg
        assert GITxn.application_args(0, 1) == second_arg

        return True

    def clear_state_program(self) -> bool:
        return True
