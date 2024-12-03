import copy
import itertools
import typing
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.context import TMP_VAR_INDICATOR
from puya.ir.optimize._call_graph import CallGraph
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator

logger = log.get_logger(__name__)


def analyse_subroutines_for_inlining(program: models.Program) -> bool:
    call_graph = CallGraph(program)
    any_marked = False
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
            if call_graph.maybe_reentrant(sub):
                sub.inline = False
                logger.debug(
                    f"function might be re-entrant: {sub.id}", location=sub.source_location
                )
            elif call_graph.reference_count(sub) == 1:
                logger.debug(f"marking single-use function {sub.id} for inlining")
                sub.inline = True
                any_marked = True
    if not any_marked:
        for sub in program.subroutines:
            if sub.inline is None and call_graph.has_maybe_inlineable_calls(sub):  # noqa: SIM102
                if _maybe_mark_for_inlining(sub):
                    any_marked = True
    if not any_marked:
        for sub in program.subroutines:
            if sub.inline is None:  # noqa: SIM102
                if _maybe_mark_for_inlining(sub):
                    any_marked = True
    return any_marked


def _maybe_mark_for_inlining(sub: models.Subroutine) -> bool:
    complexity = sum(
        len(b.phis) + len(b.ops) + len(_not_none(b.terminator).targets()) for b in sub.body
    )
    threshold = max(3, 1 + len(sub._returns) + len(sub.parameters))  # noqa: SLF001
    if complexity <= threshold:
        logger.debug(
            f"marking simple function {sub.id} for inlining" f" ({complexity=} <= {threshold=})"
        )
        sub.inline = True
        return True
    return False


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
    # make a copy of the entire block graph, and adjust register versions
    # to avoid any collisions, as well as updating block IDs
    register_offsets = defaultdict[str, int](int)
    for host_reg in host_assigned_registers:
        register_offsets[host_reg.name] = max(
            register_offsets[host_reg.name], host_reg.version + 1
        )
    new_blocks = inlined_blocks(call.target, register_offsets)
    for new_block in new_blocks:
        new_block.id = next(next_id)
    # split the block after the callsub instruction
    ops_after = block.ops[op_index + 1 :]
    del block.ops[op_index:]
    terminator_after = block.terminator
    assert terminator_after is not None
    for succ in terminator_after.unique_targets:
        succ.predecessors.remove(block)
    block.terminator = models.Goto(target=new_blocks[0], source_location=call.source_location)
    new_blocks[0].predecessors.append(block)
    # assign parameters before call
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

    returning_blocks = [
        (new_block, new_block.terminator.result)
        for new_block in new_blocks
        if isinstance(new_block.terminator, models.SubroutineReturn)
    ]
    if not returning_blocks:
        # in the case the inlined subroutine never returned, then there's no control flow
        # to pass on and no returns to assign
        return new_blocks
    # create the return block and insert as a predecessor of the original blocks target(s)
    split_block = models.BasicBlock(
        id=next(next_id),
        phis=[],
        ops=ops_after,
        terminator=terminator_after,
        predecessors=[],
        comment=f"after_inlined_{call.target.id}",
        source_location=block.source_location,
    )
    for succ in split_block.successors:
        for phi in succ.phis:
            for phi_arg in phi.args:
                if phi_arg.through == block:
                    phi_arg.through = split_block
        succ.predecessors.append(split_block)
    # replace inlined retsubs with unconditional branches to the second block half
    for new_block, _ in returning_blocks:
        new_block.terminator = models.Goto(
            target=split_block, source_location=call.source_location
        )
        split_block.predecessors.append(new_block)

    if len(returning_blocks) == 1:
        # if there is a single retsub, we can assign to the return variables in that block
        # directly without violating SSA
        ((new_block, return_values),) = returning_blocks
        if return_targets:
            new_block.ops.append(
                models.Assignment(
                    targets=return_targets,
                    source=models.ValueTuple(values=return_values, source_location=None),
                    source_location=None,
                )
            )
        return [*new_blocks, split_block]
    else:
        # otherwise when there's more than on restsub block,
        # return value(s) become phi node(s) in the second block half
        return_phis = [models.Phi(register=ret_target) for ret_target in return_targets]
        for new_block_idx, (new_block, return_values) in enumerate(returning_blocks):
            for ret_idx, ret_phi in enumerate(return_phis):
                ret_value = return_values[ret_idx]
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

        split_block.phis = return_phis
        attrs.validate(split_block)
        return [*new_blocks, split_block]


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
