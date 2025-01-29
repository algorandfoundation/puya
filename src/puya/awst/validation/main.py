from puya.awst import nodes as awst_nodes
from puya.awst.validation.arc4_copy import ARC4CopyValidator
from puya.awst.validation.base_invoker import BaseInvokerValidator
from puya.awst.validation.immutable import ImmutableValidator
from puya.awst.validation.inner_transactions import (
    InnerTransactionsValidator,
    InnerTransactionUsedInALoopValidator,
    StaleInnerTransactionsValidator,
)
from puya.awst.validation.labels import LabelsValidator
from puya.awst.validation.storage import StorageTypesValidator


def validate_awst(module: awst_nodes.AWST) -> None:
    ARC4CopyValidator.validate(module)
    InnerTransactionsValidator.validate(module)
    InnerTransactionUsedInALoopValidator.validate(module)
    StaleInnerTransactionsValidator.validate(module)
    BaseInvokerValidator.validate(module)
    StorageTypesValidator.validate(module)
    LabelsValidator.validate(module)
    ImmutableValidator.validate(module)
