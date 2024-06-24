from puya.awst import nodes as awst_nodes
from puya.awst_build.validation.arc4_copy import ARC4CopyValidator
from puya.awst_build.validation.base_invoker import BaseInvokerValidator
from puya.awst_build.validation.inner_transactions import (
    InnerTransactionsValidator,
    InnerTransactionUsedInALoopValidator,
    StaleInnerTransactionsValidator,
)
from puya.awst_build.validation.scratch_slots import ScratchSlotReservationValidator


def validate_awst(module: awst_nodes.Module) -> None:
    ARC4CopyValidator.validate(module)
    ScratchSlotReservationValidator.validate(module)
    InnerTransactionsValidator.validate(module)
    InnerTransactionUsedInALoopValidator.validate(module)
    StaleInnerTransactionsValidator.validate(module)
    BaseInvokerValidator.validate(module)
