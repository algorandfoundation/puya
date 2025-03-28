import copy
import itertools
import typing
from collections import defaultdict
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence

import attrs
import networkx as nx  # type: ignore[import-untyped]

from puya import log
from puya.ir import models
from puya.ir.optimize._call_graph import CallGraph
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.optimize.intrinsic_simplification import COMPILE_TIME_CONSTANT_OPS
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.utils import lazy_setdefault, not_none

logger = log.get_logger(__name__)


def analyse_subroutines_for_inlining(
    context: IROptimizationContext,
    program: models.Program,
    routable_method_ids: Collection[str] | None,
) -> None:
    context.inlineable_calls.clear()
    context.constant_with_constant_args.clear()

    call_graph = CallGraph(program)
    for sub in program.subroutines:
        if sub.inline is False:
            pass  # nothing to do
        elif any(phi.args for phi in sub.entry.phis):
            logger.debug(
                f"function has phi node(s) with arguments in entry block: {sub.id}",
                location=sub.source_location,
            )
            if sub.inline is True:
                logger.warning(
                    "function not suitable for inlining due to complex control flow",
                    location=sub.source_location,
                )
            sub.inline = False
        elif call_graph.is_auto_recursive(sub):
            logger.debug(f"function is auto-recursive: {sub.id}", location=sub.source_location)
            if sub.inline is True:
                logger.warning("unable to inline recursive function", location=sub.source_location)
            sub.inline = False
        elif sub.inline is True:
            for callee_id, _ in call_graph.callees(sub):
                if not call_graph.has_path(sub.id, callee_id):
                    context.inlineable_calls.add((callee_id, sub.id))
                else:
                    logger.warning(
                        f"not inlining call from {callee_id} to {sub.id}"
                        f" because call may be re-entrant",
                        location=sub.source_location,
                    )
        else:
            typing.assert_type(sub.inline, None)
    if context.options.optimization_level == 0:
        return

    # for optimization levels below 2, skip auto-inlining routable methods into the approval
    # program. mostly this can be beneficial in terms of #ops, but not always.
    # also, it impacts the debugging experience
    skip_routable_ids = frozenset[str]()
    if context.options.optimization_level < 2:
        skip_routable_ids = frozenset(routable_method_ids or ())

    for sub in program.subroutines:
        if sub.inline is None:
            if _is_trivial(sub):
                # special case for trivial methods, even when routable
                logger.debug(f"marking trivial method {sub.id} as inlineable")
                for callee_id, _ in call_graph.callees(sub):
                    # don't need to check re-entrancy here since there's no callsub
                    context.inlineable_calls.add((callee_id, sub.id))
            elif sub.id not in skip_routable_ids:
                match call_graph.callees(sub):
                    case [(callee_id, 1)]:
                        assert (
                            callee_id != sub.id
                        ), f"function {sub.id} is auto-recursive and disconnected"
                        logger.debug(f"marking single-use function {sub.id} for inlining")
                        context.inlineable_calls.add((callee_id, sub.id))
    if context.inlineable_calls:
        return
    for sub in program.subroutines:
        if sub.inline is None and sub.id not in skip_routable_ids:
            complexity = sum(
                len(b.phis) + len(b.ops) + len(not_none(b.terminator).targets()) for b in sub.body
            )
            threshold = max(3, 1 + len(sub._returns) + len(sub.parameters))  # noqa: SLF001
            if complexity <= threshold:
                logger.debug(
                    f"marking simple function {sub.id} for inlining"
                    f" ({complexity=} <= {threshold=})"
                )
                for callee_id, _ in call_graph.callees(sub):
                    if not call_graph.has_path(sub.id, callee_id):
                        context.inlineable_calls.add((callee_id, sub.id))


def _is_trivial(sub: models.Subroutine) -> bool:
    match sub.body:
        case [models.BasicBlock(phis=[], ops=[])]:
            return True
    return False


def perform_subroutine_inlining(
    context: IROptimizationContext, subroutine: models.Subroutine
) -> bool:
    inline_calls_to = {
        to_id for from_id, to_id in context.inlineable_calls if from_id == subroutine.id
    }
    if not (inline_calls_to or context.options.optimization_level >= 2):
        return False
    modified = False
    blocks_to_visit = subroutine.body.copy()
    max_block_id = max(not_none(block.id) for block in blocks_to_visit)
    next_id = itertools.count(max_block_id + 1)
    while blocks_to_visit:
        block = blocks_to_visit.pop()
        for op_index, op in enumerate(block.ops):
            match op:
                case models.Assignment(
                    targets=return_targets, source=models.InvokeSubroutine() as call
                ):
                    pass
                case models.InvokeSubroutine() as call:
                    return_targets = []
                case _:
                    continue
            if call.target.id in inline_calls_to:
                logger.debug(
                    f"inlining call to {call.target.id} in {subroutine.id}",
                    location=op.source_location,
                )
            elif (
                context.options.optimization_level >= 2
                and call.target.inline is None
                and all(isinstance(arg, models.Constant) for arg in call.args)
                and lazy_setdefault(
                    context.constant_with_constant_args,
                    call.target.id,
                    lambda _: _ConstantFunctionDetector.is_constant_with_constant_args(
                        call.target
                    ),
                )
            ):
                logger.debug(
                    f"constant function call to {call.target.id} in {subroutine.id}",
                    location=op.source_location,
                )
            else:
                continue

            remainder, created_blocks = _inline_call(
                block,
                call,
                next_id,
                op_index,
                return_targets,
                list(subroutine.get_assigned_registers()),
            )
            # only visit the remainder of the block, the newly created blocks
            # come from a different subroutine, so shouldn't be tested for inlining
            # within the curren subroutine
            blocks_to_visit.append(remainder)
            created_blocks.append(remainder)
            idx_after_block = subroutine.body.index(block) + 1
            subroutine.body[idx_after_block:idx_after_block] = created_blocks
            modified = True
            break  # we're done with this block, since it's been split
    return modified


def _inline_call(
    block: models.BasicBlock,
    call: models.InvokeSubroutine,
    next_id: Iterator[int],
    op_index: int,
    return_targets: Sequence[models.Register],
    host_assigned_registers: list[models.Register],
) -> tuple[models.BasicBlock, list[models.BasicBlock]]:
    # make a copy of the entire block graph, and adjust register versions
    # to avoid any collisions, as well as updating block IDs
    register_offsets = defaultdict[str, int](int)
    for host_reg in host_assigned_registers:
        register_offsets[host_reg.name] = max(
            register_offsets[host_reg.name], host_reg.version + 1
        )
    new_blocks = _inlined_blocks(call.target, register_offsets)
    for new_block in new_blocks:
        new_block.id = next(next_id)
    # split the block after the callsub instruction
    ops_after = block.ops[op_index + 1 :]
    del block.ops[op_index:]
    terminator_after = block.terminator
    assert terminator_after is not None
    for succ in terminator_after.unique_targets:
        succ.predecessors.remove(block)
    inlined_entry = new_blocks[0]
    block.terminator = models.Goto(target=inlined_entry, source_location=call.source_location)
    inlined_entry.predecessors.append(block)
    for phi in inlined_entry.phis:
        # TODO: assign undefined and use that as phi arg so we can inline phi nodes with args.
        #       this requires finding a new register though, and is quite hard to write code
        #       that would trigger this, so leaving for now
        assert not phi.args, "entry phi with arguments should have been prevented from inlining"
        inlined_entry.ops.insert(
            0,
            models.Assignment(
                targets=[phi.register],
                source=models.Undefined(ir_type=phi.ir_type, source_location=phi.source_location),
                source_location=phi.source_location,
            ),
        )
    inlined_entry.phis.clear()
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
    # create the return block and insert as a predecessor of the original blocks target(s)
    remainder = models.BasicBlock(
        id=next(next_id),
        phis=[],
        ops=ops_after,
        terminator=terminator_after,
        predecessors=[],
        comment=f"after_inlined_{call.target.id}",
        source_location=block.source_location,
    )
    for succ in remainder.successors:
        for phi in succ.phis:
            for phi_arg in phi.args:
                if phi_arg.through == block:
                    phi_arg.through = remainder
        succ.predecessors.append(remainder)
    # replace inlined retsubs with unconditional branches to the second block half
    for new_block, _ in returning_blocks:
        new_block.terminator = models.Goto(target=remainder, source_location=call.source_location)
        remainder.predecessors.append(new_block)

    num_returns = len(returning_blocks)
    if num_returns == 1:
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
    elif num_returns > 1:
        # otherwise when there's more than on restsub block,
        # return value(s) become phi node(s) in the second block half
        return_phis = [models.Phi(register=ret_target) for ret_target in return_targets]
        for new_block_idx, (new_block, return_values) in enumerate(returning_blocks):
            for ret_idx, ret_phi in enumerate(return_phis):
                ret_value = return_values[ret_idx]
                if not isinstance(ret_value, models.Register):
                    tmp_value = ret_value
                    tmp_reg_name = f"{call.target.id}{models.TMP_VAR_INDICATOR}{ret_idx}"
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

        remainder.phis = return_phis
    return remainder, new_blocks


def _inlined_blocks(
    sub: models.Subroutine, register_offsets: Mapping[str, int]
) -> list[models.BasicBlock]:
    ref_collector = _SubroutineReferenceCollector()
    ref_collector.visit_all_blocks(sub.body)
    assert (
        sub not in ref_collector.subroutines
    ), "auto recursive blocks should already be filtered out"
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


class _NonConstantFunctionError(Exception):
    pass


class _ConstantFunctionDetector(IRTraverser):
    def __init__(self) -> None:
        self._block_graph = nx.DiGraph()

    def has_cycle(self, *, start_from: int | None = None) -> bool:
        try:
            nx.find_cycle(self._block_graph, source=start_from)
        except nx.NetworkXNoCycle:
            return False
        else:
            return True

    @classmethod
    def is_constant_with_constant_args(cls, sub: models.Subroutine) -> bool:
        """Detect if a function is constant assuming all argument are constants"""
        visitor = cls()
        try:
            visitor.visit_all_blocks(sub.body)
        except _NonConstantFunctionError:
            return False
        return not visitor.has_cycle(start_from=sub.entry.id)

    @typing.override
    def visit_block(self, block: models.BasicBlock) -> None:
        super().visit_block(block)
        self._block_graph.add_node(block.id)
        for target in block.successors:
            self._block_graph.add_edge(block.id, target.id)

    @typing.override
    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> None:
        raise _NonConstantFunctionError

    @typing.override
    def visit_template_var(self, deploy_var: models.TemplateVar) -> None:
        raise _NonConstantFunctionError

    @typing.override
    def visit_compiled_contract_reference(self, const: models.CompiledContractReference) -> None:
        raise _NonConstantFunctionError

    @typing.override
    def visit_compiled_logicsig_reference(self, const: models.CompiledLogicSigReference) -> None:
        raise _NonConstantFunctionError

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        if intrinsic.op.code not in COMPILE_TIME_CONSTANT_OPS:
            raise _NonConstantFunctionError
        super().visit_intrinsic_op(intrinsic)

    @typing.override
    def visit_itxn_constant(self, const: models.ITxnConstant) -> None:
        raise _NonConstantFunctionError

    @typing.override
    def visit_inner_transaction_field(self, field: models.InnerTransactionField) -> None:
        raise _NonConstantFunctionError
