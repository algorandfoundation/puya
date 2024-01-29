import attrs
import structlog

from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Assignment, Intrinsic
from puya.ir.visitor_mutator import IRMutator

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class IntrinsicSimplifier(IRMutator):
    modified: int = 0

    def visit_assignment(self, ass: Assignment) -> Assignment | None:
        match ass.source:
            case models.Intrinsic(
                op=AVMOp.select, args=[false, true, models.UInt64Constant(value=value)]
            ):
                # note this case is handled specially because we want to replace
                # the source with a Value, not an Intrinsic
                self.modified += 1
                ass.source = true if value else false
            case models.Intrinsic() as intrinsic:
                ass.source = self._simplify_intrinsic(intrinsic)
        return ass

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> Intrinsic | None:
        match intrinsic:
            case Intrinsic(op=AVMOp.assert_, args=[models.UInt64Constant(value=value)]):
                if value:
                    self.modified += 1
                    return None
                else:
                    # an assert 0 could be simplified to an err, but
                    # this would make it a ControlOp, so the block would
                    # need to be restructured
                    return intrinsic
            case _:
                return self._simplify_intrinsic(intrinsic)

    def _simplify_intrinsic(self, intrinsic: Intrinsic) -> Intrinsic:
        match intrinsic:
            case Intrinsic(
                op=(AVMOp.loads | AVMOp.stores as op),
                args=[models.UInt64Constant(value=slot), *rest],
            ):
                self.modified += 1
                return attrs.evolve(
                    intrinsic,
                    immediates=[slot],
                    args=rest,
                    op=AVMOp.load if op == AVMOp.loads else AVMOp.store,
                )
            case Intrinsic(
                op=(AVMOp.extract3 | AVMOp.extract),
                args=[
                    models.Value(atype=AVMType.bytes),
                    models.UInt64Constant(value=S),
                    models.UInt64Constant(value=L),
                ],
            ) if S <= 255 and 1 <= L <= 255:
                # note the lower bound of 1 on length, extract with immediates vs extract3
                # have *very* different behaviour if the length is 0
                self.modified += 1
                return attrs.evolve(
                    intrinsic, immediates=[S, L], args=intrinsic.args[:1], op=AVMOp.extract
                )
            case Intrinsic(
                op=AVMOp.substring3,
                args=[
                    models.Value(atype=AVMType.bytes),
                    models.UInt64Constant(value=S),
                    models.UInt64Constant(value=E),
                ],
            ) if S <= 255 and E <= 255:
                self.modified += 1
                return attrs.evolve(
                    intrinsic, immediates=[S, E], args=intrinsic.args[:1], op=AVMOp.substring
                )
            case Intrinsic(
                op=AVMOp.replace3,
                args=[a, models.UInt64Constant(value=S), b],
            ) if S <= 255:
                self.modified += 1
                return attrs.evolve(intrinsic, immediates=[S], args=[a, b], op=AVMOp.replace2)
            case Intrinsic(
                op=AVMOp.args,
                args=[models.UInt64Constant(value=idx)],
            ) if idx <= 255:
                self.modified += 1
                return attrs.evolve(intrinsic, op=AVMOp.arg, immediates=[idx], args=[])
        return intrinsic

    @classmethod
    def apply(cls, to: models.Subroutine) -> int:
        replacer = cls()
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified


def intrinsic_simplifier(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = IntrinsicSimplifier.apply(subroutine)
    return modified > 0
