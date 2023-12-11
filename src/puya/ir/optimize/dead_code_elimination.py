from collections.abc import Iterator, Set
from typing import Iterable, Sequence

import attrs
import structlog

from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models, visitor
from puya.ir.ssa import TrivialPhiRemover

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


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
        super().visit_phi(phi)
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
