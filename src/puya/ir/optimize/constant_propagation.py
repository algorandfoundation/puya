import attrs
import structlog

from puya.context import CompileContext
from puya.ir import models
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
