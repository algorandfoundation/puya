from puya.awst import nodes as awst_nodes

from puyapy.awst_build.validation.arc4_copy import ARC4CopyValidator
from puyapy.awst_build.validation.base_invoker import BaseInvokerValidator
from puyapy.awst_build.validation.inner_transactions import (
    InnerTransactionsValidator,
    InnerTransactionUsedInALoopValidator,
    StaleInnerTransactionsValidator,
)
from puyapy.awst_build.validation.labels import LabelsValidator
from puyapy.awst_build.validation.scratch_slots import ScratchSlotReservationValidator
from puyapy.awst_build.validation.storage import StorageTypesValidator


def validate_awst(module: awst_nodes.AWST) -> None:
    ARC4CopyValidator.validate(module)
    ScratchSlotReservationValidator.validate(module)
    InnerTransactionsValidator.validate(module)
    InnerTransactionUsedInALoopValidator.validate(module)
    StaleInnerTransactionsValidator.validate(module)
    BaseInvokerValidator.validate(module)
    StorageTypesValidator.validate(module)
    LabelsValidator.validate(module)
