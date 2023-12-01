import attrs
import structlog

from wyvern.context import CompileContext
from wyvern.ir import models
from wyvern.ir.ssa import TrivialPhiRemover
from wyvern.ir.visitor_mutator import IRMutator

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


def simplify_conditional_branches(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    changes = False
    modified_phis = []
    for block in subroutine.body:
        terminator = block.terminator
        # TODO: implement similar propagator for models.Switch
        if isinstance(terminator, models.ConditionalBranch) and isinstance(
            terminator.condition, models.UInt64Constant
        ):
            if terminator.condition.value == 0:
                goto, other = terminator.zero, terminator.non_zero
            else:
                goto, other = terminator.non_zero, terminator.zero
            block.terminator = models.Goto(source_location=terminator.source_location, target=goto)
            if other is not goto:
                other.predecessors.remove(block)
                for other_phi in other.phis:
                    other_phi.args = [arg for arg in other_phi.args if arg.through is not block]
                    modified_phis.append(other_phi)
            changes = True
            logger.debug(f"ConditionalBranch {terminator} simplified to {block.terminator}")
    for phi in modified_phis:
        TrivialPhiRemover.try_remove(phi, subroutine.body)
    return changes
