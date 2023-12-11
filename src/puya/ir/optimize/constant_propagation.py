import attrs
import structlog

from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import Assignment, Intrinsic
from puya.ir.ssa import TrivialPhiRemover
from puya.ir.visitor_mutator import IRMutator

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class ConstantReplacer(IRMutator):
    constants: dict[models.Register, models.Constant]
    modified: int = 0

    @classmethod
    def apply(
        cls, constants: dict[models.Register, models.Constant], to: models.Subroutine
    ) -> int:
        if not constants:
            return 0
        replacer = cls(constants)
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified

    def visit_register(self, reg: models.Register) -> models.Register:
        if self.is_target_context or isinstance(self.current_op, models.Phi):
            return reg
        try:
            const = self.constants[reg]
        except KeyError:
            return reg
        self.modified += 1
        return const  # type: ignore[return-value]


def gather_constants(subroutine: models.Subroutine) -> dict[models.Register, models.Constant]:
    constants = {}
    for block in subroutine.body:
        for op in block.ops:
            match op:
                case models.Assignment(targets=[register], source=models.Constant() as constant):
                    constants[register] = constant
    return constants


def constant_replacer(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    constants = gather_constants(subroutine)
    modified = ConstantReplacer.apply(constants, to=subroutine)
    return modified > 0


@attrs.define
class IntrinsicSimplifier(IRMutator):
    modified: int = 0

    def visit_assignment(self, ass: Assignment) -> Assignment | None:
        match ass.source:
            case models.Intrinsic(
                op=AVMOp.select, args=[false, true, models.UInt64Constant(value=value)]
            ):
                self.modified += 1
                ass.source = true if value else false
        return ass

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> Intrinsic | None:
        match intrinsic:
            case Intrinsic(op=AVMOp.assert_, args=[models.UInt64Constant(value=value)]):
                if value:
                    self.modified += 1
                    return None
            case Intrinsic(
                op=(AVMOp.extract3 | AVMOp.extract),
                args=[
                    models.Value(atype=AVMType.bytes),
                    models.UInt64Constant(value=S),
                    models.UInt64Constant(value=L),
                ],
            ) if S <= 255 and L <= 255:
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


# the ratio of default cases to all cases when a match of constant values
# can be simplified to a goto-nth
SWITCH_SPARSENESS_SIMPLIFICATION_RATIO = 0.5


def can_simplify_switch(switch: models.Switch) -> bool:
    total_targets = 0
    for case in switch.cases:
        if not isinstance(case, models.UInt64Constant):
            return False
        total_targets = max(total_targets, case.value)
    default_targets = total_targets - len(switch.cases)
    return default_targets < (total_targets * SWITCH_SPARSENESS_SIMPLIFICATION_RATIO)


def simplify_conditional_branches(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    changes = False
    modified_phis = []

    def remove_target(parent: models.BasicBlock, to_remove: models.BasicBlock) -> None:
        to_remove.predecessors.remove(parent)
        for other_phi in to_remove.phis:
            other_phi.args = [arg for arg in other_phi.args if arg.through is not parent]
            modified_phis.append(other_phi)

    for block in subroutine.body:
        terminator = block.terminator
        match terminator:
            case models.ConditionalBranch(
                condition=models.UInt64Constant(value=value), zero=zero, non_zero=non_zero
            ):
                if value == 0:
                    goto, other = zero, non_zero
                else:
                    goto, other = non_zero, zero
                block.terminator = models.Goto(
                    source_location=terminator.source_location, target=goto
                )
                if other is not goto:
                    remove_target(block, other)
            case models.Switch(
                value=models.Value(atype=AVMType.uint64) as value,
                cases=cases,
                default=default_block,
                source_location=source_location,
            ) as switch if can_simplify_switch(switch):
                # reduce to GotoNth
                block_map = dict[int, models.BasicBlock]()
                for case, case_block in cases.items():
                    assert isinstance(case, models.UInt64Constant)
                    block_map[case.value] = case_block
                max_value = max(block_map)
                block.terminator = models.GotoNth(
                    value=value,
                    blocks=[block_map.get(i, default_block) for i in range(max_value + 1)],
                    source_location=source_location,
                    default=default_block,
                )
            case models.GotoNth(
                value=models.UInt64Constant(value=value),
                blocks=blocks,
                default=default_block,
            ):
                goto = blocks[value] if value < len(blocks) else default_block
                block.terminator = models.Goto(
                    source_location=terminator.source_location, target=goto
                )
                for target in terminator.targets():
                    if target is not goto:
                        remove_target(block, target)
            # TODO: do these belong in constant_propagation?
            case models.GotoNth(
                value=value,
                blocks=[zero],  # the constant here is the size of blocks
                default=non_zero,
            ):  # reduces to ConditionalBranch
                block.terminator = models.ConditionalBranch(
                    condition=value,
                    zero=zero,
                    non_zero=non_zero,
                    source_location=terminator.source_location,
                )
            case _:
                continue
        changes = True
        original_terminator_name = terminator.__class__.__name__
        logger.debug(f"{original_terminator_name} {terminator} simplified to {block.terminator}")
    for phi in modified_phis:
        TrivialPhiRemover.try_remove(phi, subroutine.body)
    return changes
