import copy
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models, visitor
from puya.ir.context import TMP_VAR_INDICATOR
from puya.ir.optimize._call_graph import CallGraph
from puya.ir.ssa import TrivialPhiRemover
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.utils import unique

logger = log.get_logger(__name__)


_ALWAYS_INLINE = False


def analyse_subroutines_for_inlining(program: models.Program) -> None:
    collector = _SubroutineCallCounter()
    collector.visit_subroutine(program.main)
    call_graph: CallGraph | None = None
    for sub in program.subroutines:
        if sub.inline is False:
            pass  # nothing to do
        elif sub.entry.phis:
            logger.debug(
                f"function has phi node(s) in entry block: {sub.id}",
                location=sub.source_location,
            )
            if sub.inline is True:
                logger.warning(
                    "function not suitable for inlining due to complex control flow",
                    location=sub.source_location,
                )
            sub.inline = False
        elif sub.inline is None:
            reference_count = collector.subroutines.get(sub, 0)
            if reference_count > 1:
                if call_graph is None:
                    call_graph = CallGraph.build(program)
                if call_graph.maybe_reentrant(sub):
                    sub.inline = False
                    logger.debug(
                        f"function might be re-entrant: {sub.id}", location=sub.source_location
                    )
                    continue
            if reference_count == 1:
                logger.debug(f"marking single-use function {sub.id} for inlining")
                sub.inline = True
            elif (
                complexity := sum(
                    len(b.phis) + len(b.ops) + len(_not_none(b.terminator).targets())
                    for b in sub.body
                )
            ) <= (threshold := max(3, len(sub.returns) + len(sub.parameters))):
                logger.debug(
                    f"marking simple function {sub.id} for inlining"
                    f" ({complexity=} <= {threshold=})"
                )
                sub.inline = True
            elif _ALWAYS_INLINE:
                sub.inline = True


def perform_subroutine_inlining(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    blocks_to_visit = subroutine.body.copy()
    max_block_id = max(_not_none(block.id) for block in blocks_to_visit)
    next_id = itertools.count(max_block_id + 1)
    while blocks_to_visit:
        block = blocks_to_visit.pop()
        for op_index, op in enumerate(block.ops):
            match op:
                case models.Assignment(
                    targets=return_targets, source=models.InvokeSubroutine() as call
                ) if call.target.inline:
                    pass
                case models.InvokeSubroutine() as call if call.target.inline:
                    return_targets = []
                case _:
                    continue
            if subroutine == call.target:
                logger.debug("unable to inline recursive call", location=call.source_location)
                continue
            if call.target.entry.phis:
                logger.debug(
                    "unable to inline call to function with phi nodes in entry block",
                    location=call.source_location,
                )
                continue
            logger.debug(
                f"inlining call to {call.target.id} in {subroutine.id}",
                location=op.source_location,
            )
            created_blocks = _inline_call(
                block,
                call,
                next_id,
                op_index,
                return_targets,
                list(subroutine.get_assigned_registers()),
            )
            blocks_to_visit.extend(created_blocks)
            idx_after_block = subroutine.body.index(block) + 1
            subroutine.body[idx_after_block:idx_after_block] = created_blocks
            for block in created_blocks:
                for phi in block.phis:
                    TrivialPhiRemover.try_remove(phi, subroutine.body)  # TODO: shouldn't be needed
            subroutine.validate_with_ssa()
            modified = True
            break
    return modified


def _inline_call(
    block: models.BasicBlock,
    call: models.InvokeSubroutine,
    next_id: Iterator[int],
    op_index: int,
    return_targets: Sequence[models.Register],
    host_assigned_registers: list[models.Register],
) -> list[models.BasicBlock]:
    # 1. make a copy of the entire block graph, and adjust register versions
    #    to avoid any collisions, as well as updating block IDs
    register_offsets = defaultdict[str, int](int)
    for host_reg in host_assigned_registers:
        register_offsets[host_reg.name] = max(
            register_offsets[host_reg.name], host_reg.version + 1
        )
    new_blocks = inlined_blocks(call.target, register_offsets)
    for new_block in new_blocks:
        new_block.id = next(next_id)
    # 2. split the block after the callsub instruction
    # 2.a. create the return block
    return_block = models.BasicBlock(
        id=next(next_id),
        phis=[],
        ops=block.ops[op_index + 1 :],
        terminator=block.terminator,
        predecessors=[],
        comment=f"split from inlining callsub op of {block.id} at index {op_index}",
        source_location=block.source_location,
    )
    for succ in unique(return_block.successors):
        for phi in succ.phis:
            for phi_arg in phi.args:
                if phi_arg.through == block:
                    phi_arg.through = return_block
        succ.predecessors.remove(block)
        succ.predecessors.append(return_block)
    # 2.b. update the current block
    del block.ops[op_index:]
    block.terminator = models.Goto(target=new_blocks[0], source_location=call.source_location)
    new_blocks[0].predecessors.append(block)
    # 3. assign parameters in current block
    for arg, param in zip(call.args, call.target.parameters, strict=True):
        updated_param = models.Register(
            name=param.name,
            ir_type=param.ir_type,
            version=param.version + register_offsets[param.name],
            source_location=param.source_location,
        )
        block.ops.append(
            models.Assignment(
                targets=[updated_param], source=arg, source_location=arg.source_location
            )
        )
    # 4. replace returns with unconditional branches to the second block half
    return_phis = [models.Phi(register=ret_target) for ret_target in return_targets]
    for new_block_idx, new_block in enumerate(new_blocks):
        if not isinstance(new_block.terminator, models.SubroutineReturn):
            continue
        for ret_idx, ret_phi in enumerate(return_phis):
            ret_value = new_block.terminator.result[ret_idx]
            if not isinstance(ret_value, models.Register):
                tmp_value = ret_value
                tmp_reg_name = f"{call.target.id}{TMP_VAR_INDICATOR}{ret_idx}"
                ret_value = models.Register(
                    ir_type=ret_value.ir_type,
                    source_location=ret_value.source_location,
                    name=tmp_reg_name,
                    version=new_block_idx + register_offsets[tmp_reg_name],
                )
                new_block.ops.append(
                    models.Assignment(
                        targets=[ret_value],
                        source=tmp_value,
                        source_location=tmp_value.source_location,
                    )
                )
            ret_phi.args.append(models.PhiArgument(value=ret_value, through=new_block))
        new_block.terminator = models.Goto(
            target=return_block, source_location=call.source_location
        )
        return_block.predecessors.append(new_block)
    # 5. return value(s) become phi node(s) in the second block half
    return_block.phis = return_phis
    return [*new_blocks, return_block]


def _not_none[T](x: T | None) -> T:
    assert x is not None
    return x


def inlined_blocks(
    sub: models.Subroutine, register_offsets: Mapping[str, int]
) -> list[models.BasicBlock]:
    ref_collector = _SubroutineReferenceCollector()
    ref_collector.visit_all_blocks(sub.body)
    memo = {id(s): s for s in ref_collector.subroutines}
    blocks = copy.deepcopy(sub.body, memo=memo)
    _OffsetRegisterVersions.apply(blocks, register_offsets=register_offsets)
    return blocks


@attrs.define
class _OffsetRegisterVersions(IRMutator):
    register_offsets: Mapping[str, int]

    @classmethod
    def apply(
        cls, blocks: Iterable[models.BasicBlock], *, register_offsets: Mapping[str, int]
    ) -> None:
        replacer = cls(register_offsets=register_offsets)
        for block in blocks:
            replacer.visit_block(block)

    def visit_register(self, reg: models.Register) -> models.Register:
        return models.Register(
            name=reg.name,
            ir_type=reg.ir_type,
            version=reg.version + self.register_offsets[reg.name],
            source_location=reg.source_location,
        )


@attrs.define
class _SubroutineReferenceCollector(IRTraverser):
    subroutines: set[models.Subroutine] = attrs.field(factory=set)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        self.subroutines.add(callsub.target)
        super().visit_invoke_subroutine(callsub)


@attrs.define
class _SubroutineCallCounter(visitor.IRTraverser):
    subroutines: dict[models.Subroutine, int] = attrs.field(factory=dict)

    def visit_subroutine(self, subroutine: models.Subroutine) -> None:
        try:
            self.subroutines[subroutine] += 1
        except KeyError:
            self.subroutines[subroutine] = 1
            self.visit_all_blocks(subroutine.body)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        self.visit_subroutine(callsub.target)
