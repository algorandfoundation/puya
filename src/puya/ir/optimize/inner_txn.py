from collections.abc import Mapping

import attrs

from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize.constant_propagation import gather_constants
from puya.ir.visitor_mutator import IRMutator


def inner_txn_field_replacer(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = IntrinsicFieldReplacer.apply(to=subroutine)
    return modified > 0


@attrs.define
class IntrinsicFieldReplacer(IRMutator):
    constants: Mapping[models.Register, models.Constant]
    modified: int = 0

    @classmethod
    def apply(cls, to: models.Subroutine) -> int:
        constants = gather_constants(to)
        replacer = cls(constants)
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified

    def _get_constant(self, value: models.Value, default: int | None = None) -> int | None:
        match value:
            case models.UInt64Constant(value=int_value) | models.ITxnConstant(value=int_value):
                return int_value
            case models.Register() as group_reg if (
                (const := self.constants.get(group_reg))
                and isinstance(const, models.UInt64Constant | models.ITxnConstant)
            ):
                return const.value
            case _:
                return default

    def visit_inner_transaction_field(
        self, field: models.InnerTransactionField
    ) -> models.InnerTransactionField | models.Intrinsic:
        group_index = self._get_constant(field.group_index)
        if group_index is None:
            return field
        is_last_in_group = self._get_constant(field.is_last_in_group, 0)
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
