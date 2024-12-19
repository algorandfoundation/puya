import attrs

from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.visitor_mutator import IRMutator


def inner_txn_field_replacer(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = IntrinsicFieldReplacer.apply(to=subroutine)
    return modified > 0


@attrs.define
class IntrinsicFieldReplacer(IRMutator):
    modified: int = 0

    @classmethod
    def apply(cls, to: models.Subroutine) -> int:
        replacer = cls()
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified

    def visit_inner_transaction_field(
        self, field: models.InnerTransactionField
    ) -> models.InnerTransactionField | models.Intrinsic:
        match field.group_index:
            case models.ITxnConstant(value=group_index):
                pass
            case _:
                return field
        match field.is_last_in_group:
            case models.UInt64Constant(value=is_last_in_group):
                pass
            case _:
                is_last_in_group = 0
        self.modified += 1
        return (
            models.Intrinsic(
                op=AVMOp.itxnas if field.array_index else AVMOp.itxn,
                immediates=[field.field],
                args=[field.array_index] if field.array_index else [],
                source_location=field.source_location,
            )
            if is_last_in_group
            else models.Intrinsic(
                op=AVMOp.gitxnas if field.array_index else AVMOp.gitxn,
                immediates=[group_index, field.field],
                args=[field.array_index] if field.array_index else [],
                source_location=field.source_location,
            )
        )
