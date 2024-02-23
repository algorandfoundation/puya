from puya.awst import nodes as awst_nodes
from puya.awst_build.context import ASTConversionContext
from puya.awst_build.validation.arc4_copy import ARC4CopyValidator
from puya.awst_build.validation.inner_transactions import InnerTransactionsValidator
from puya.awst_build.validation.scratch_slots import ScratchSlotReservationValidator


def validate_awst(context: ASTConversionContext, module: awst_nodes.Module) -> None:
    ARC4CopyValidator.validate(context, module)
    ScratchSlotReservationValidator.validate(context, module)
    InnerTransactionsValidator.validate(context, module)
