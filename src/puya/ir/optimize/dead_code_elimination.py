from collections.abc import Iterator, Set
from typing import Iterable, Sequence

import attrs
import structlog

from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models, visitor
from puya.ir.ssa import TrivialPhiRemover
from puya.utils import StableSet

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class SubroutineCollector(visitor.IRTraverser):
    subroutines: StableSet[models.Subroutine] = attrs.field(factory=StableSet)

    def visit_subroutine(self, subroutine: models.Subroutine) -> None:
        if subroutine not in self.subroutines:
            self.subroutines.add(subroutine)
            self.visit_all_blocks(subroutine.body)

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        self.visit_subroutine(callsub.target)


def remove_unused_subroutines(_context: CompileContext, contract_ir: models.Contract) -> bool:
    modified = False
    for program in (contract_ir.approval_program, contract_ir.clear_program):
        collector = SubroutineCollector()
        collector.visit_subroutine(program.main)
        to_keep = [p for p in program.subroutines if p in collector.subroutines]
        if to_keep != program.subroutines:
            program.subroutines = to_keep
            modified = True
    return modified


def remove_unused_variables(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = 0
    unused = UnusedRegisterCollector.collect(subroutine)
    for block, op, register in unused:
        logger.debug(f"Removing unused variable {register.local_id}")
        if isinstance(op, models.Phi):
            assert register == op.register
            block.phis.remove(op)
        else:
            assert [register] == op.targets
            block.ops.remove(op)
        modified += 1
    return modified > 0


@attrs.define
class UnusedRegisterCollector(visitor.IRTraverser):
    used: set[models.Register] = attrs.field(factory=set)
    assigned: dict[
        models.Register, tuple[models.BasicBlock, models.Assignment | models.Phi]
    ] = attrs.field(factory=dict)

    @classmethod
    def collect(
        cls, sub: models.Subroutine
    ) -> Iterable[tuple[models.BasicBlock, models.Assignment | models.Phi, models.Register]]:
        collector = cls()
        collector.visit_all_blocks(sub.body)
        for reg, (block, ass) in collector.assigned.items():
            if reg not in collector.used:
                yield block, ass, reg

    def visit_assignment(self, ass: models.Assignment) -> None:
        # only consider with sources that are side-effect free as potentially removed
        match ass:
            case models.Assignment(targets=[target], source=models.Value()):
                self.assigned[target] = (self.active_block, ass)
        ass.source.accept(self)

    def visit_phi(self, phi: models.Phi) -> None:
        # don't visit phi.register, as this would mean the phi can never be considered unused
        for arg in phi.args:
            arg.accept(self)
        self.assigned[phi.register] = (self.active_block, phi)

    def visit_register(self, reg: models.Register) -> None:
        self.used.add(reg)


def _walk_blocks(start: models.Subroutine) -> Iterator[models.BasicBlock]:
    seen = set[models.BasicBlock]()
    stack = [start.body[0]]
    while stack:
        visit = stack.pop()
        if visit not in seen:
            seen.add(visit)
            yield visit
            stack.extend(visit.successors)


def remove_unreachable_blocks(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    reachable_set = frozenset(_walk_blocks(subroutine))
    unreachable_blocks = [b for b in subroutine.body if b not in reachable_set]
    if not unreachable_blocks:
        return False

    logger.debug(f"Removing unreachable blocks: {', '.join(map(str, unreachable_blocks))}")

    reachable_blocks = []
    for block in subroutine.body:
        if block in reachable_set:
            reachable_blocks.append(block)
            if not reachable_set.issuperset(block.successors):
                raise InternalError(
                    f"Block {block} has unreachable successor(s),"
                    f" but was not marked as unreachable itself"
                )
            if not reachable_set.issuperset(block.predecessors):
                block.predecessors = [b for b in block.predecessors if b in reachable_set]
                logger.debug(f"Removed unreachable predecessors from {block}")

    UnreachablePhiArgsRemover.apply(unreachable_blocks, reachable_blocks)
    subroutine.body = reachable_blocks
    return True


@attrs.define
class UnreachablePhiArgsRemover(visitor.IRTraverser):
    _unreachable_blocks: Set[models.BasicBlock]
    _reachable_blocks: Sequence[models.BasicBlock]

    @classmethod
    def apply(
        cls,
        unreachable_blocks: Sequence[models.BasicBlock],
        reachable_blocks: Sequence[models.BasicBlock],
    ) -> None:
        collector = cls(frozenset(unreachable_blocks), reachable_blocks)
        collector.visit_all_blocks(reachable_blocks)

    def visit_phi(self, phi: models.Phi) -> None:
        args_to_remove = [a for a in phi.args if a.through in self._unreachable_blocks]
        if not args_to_remove:
            return
        logger.debug(
            "Removing unreachable phi arguments: " + ", ".join(sorted(map(str, args_to_remove)))
        )
        phi.args = [a for a in phi.args if a not in args_to_remove]
        if not phi.non_self_args:
            raise InternalError(
                f"undefined phi created when removing args through "
                f"{', '.join(map(str, self._unreachable_blocks))}"
            )
        TrivialPhiRemover.try_remove(phi, self._reachable_blocks)
