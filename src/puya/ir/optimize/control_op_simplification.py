import attrs
import structlog

from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.models import PhiArgument
from puya.ir.optimize._utils import get_definition
from puya.ir.ssa import TrivialPhiRemover
from puya.utils import unique

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


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


def simplify_control_ops(_context: CompileContext, subroutine: models.Subroutine) -> bool:
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
            case models.ConditionalBranch(
                condition=condition,
                zero=models.BasicBlock(
                    phis=[], ops=[], terminator=models.Fail(comment=fail_comment)
                ) as err_block,
                non_zero=non_zero,
                source_location=source_location,
            ):
                logger.debug("inlining condition branch to err block into an assert true")
                block.ops.append(
                    models.Intrinsic(
                        op=AVMOp.assert_,
                        args=[condition],
                        comment=fail_comment,
                        source_location=source_location,
                    )
                )
                block.terminator = models.Goto(target=non_zero, source_location=source_location)
                if err_block not in block.successors:
                    remove_target(block, err_block)
            case models.ConditionalBranch(
                condition=models.Register() as condition,
                non_zero=models.BasicBlock(
                    phis=[], ops=[], terminator=models.Fail(comment=fail_comment)
                ) as err_block,
                zero=zero,
                source_location=source_location,
            ):
                logger.debug("inlining condition branch to err block into an assert false")
                not_condition = models.Register(
                    name=f"not%{condition.name}",
                    atype=AVMType.uint64,
                    version=condition.version,
                    source_location=source_location,
                )
                if get_definition(subroutine, not_condition, should_exist=False) is None:
                    block.ops.append(
                        models.Assignment(
                            targets=[not_condition],
                            source=models.Intrinsic(
                                op=AVMOp.not_,
                                args=[condition],
                                source_location=source_location,
                            ),
                            source_location=source_location,
                        )
                    )
                block.ops.append(
                    models.Intrinsic(
                        op=AVMOp.assert_,
                        args=[not_condition],
                        comment=fail_comment,
                        source_location=source_location,
                    )
                )
                block.terminator = models.Goto(target=zero, source_location=source_location)
                if err_block not in block.successors:
                    remove_target(block, err_block)
            case models.ConditionalBranch(
                condition=models.Register() as condition,
            ) as branch if (
                isinstance(defn := get_definition(subroutine, condition), models.Assignment)
                and isinstance(defn.source, models.Intrinsic)
                and defn.source.op is AVMOp.not_
            ):
                logger.debug(
                    f"simplified branch on !{condition} by swapping zero and non-zero targets"
                )
                block.terminator = attrs.evolve(
                    branch,
                    zero=branch.non_zero,
                    non_zero=branch.zero,
                    condition=defn.source.args[0],
                )
            case models.Switch(
                value=models.Value(atype=AVMType.uint64) as value,
                cases=cases,
                default=models.ControlOp(
                    unique_targets=[default_block], can_exit=False, source_location=default_sloc
                ),
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
                    default=models.Goto(source_location=default_sloc, target=default_block),
                )
            case models.GotoNth(
                value=models.UInt64Constant(value=value),
                blocks=blocks,
                default=models.ControlOp(unique_targets=[default_block], can_exit=False),
            ):
                goto = blocks[value] if value < len(blocks) else default_block
                block.terminator = models.Goto(
                    source_location=terminator.source_location, target=goto
                )
                for target in unique(terminator.targets()):
                    if target is not goto:
                        remove_target(block, target)
            case models.GotoNth(
                value=value,
                blocks=[zero],  # the constant here is the size of blocks
                default=models.ControlOp(unique_targets=[non_zero], can_exit=False),
            ):  # reduces to ConditionalBranch
                block.terminator = models.ConditionalBranch(
                    condition=value,
                    zero=zero,
                    non_zero=non_zero,
                    source_location=terminator.source_location,
                )
            # if the default target of a Switch/GotoNth is just a single ControlOp,
            # inline that ControlOp instead
            case (
                models.Switch(
                    default=models.ControlOp(unique_targets=[default_block], can_exit=False)
                )
                | models.GotoNth(
                    default=models.ControlOp(unique_targets=[default_block], can_exit=False)
                )
            ) as fallthrough_terminator if (
                # only if the default_block is empty
                not (default_block.ops or default_block.phis)
                # and only if there is no overlap between the default_block successor and
                # switch/gotonth targets, otherwise even though default_block appears empty now,
                # it's actually filled with phi-node magic we need to retain
                # TODO: this could be narrowed to check if the phi args are non-matching instead.
                #       you could potentially end up with matching phi args coming from block
                #       and default_block if there's an earlier control flow split before block
                #       and a merge to default_block
                and set(default_block.successors).isdisjoint(fallthrough_terminator.targets())
            ):
                assert (
                    default_block.terminator is not None
                ), f"block {default_block} should already have been terminated"
                block.terminator = attrs.evolve(
                    fallthrough_terminator, default=default_block.terminator
                )
                # remove this block from the predecessors of default_block,
                # if default_block is not targeted through one of the non-default cases
                if default_block not in block.terminator.targets():
                    remove_target(block, default_block)
                # add this block as a predecessor to any new targets
                # and update relevant phi args in successor
                for succ in unique(block.successors):
                    if block not in succ.predecessors:
                        logger.debug(
                            f"adding {block} as a predecessor of {succ}"
                            f" due to inlining of {default_block}"
                        )
                        succ.predecessors.append(block)
                        _copy_inlined_phi_args(succ, default_block, block)
            case _:
                continue
        changes = True
        logger.debug(f"simplified terminator of {block} from {terminator} to {block.terminator}")
    for phi in modified_phis:
        TrivialPhiRemover.try_remove(phi, subroutine.body)
    return changes


def _copy_inlined_phi_args(
    phi_block: models.BasicBlock, inlined_block: models.BasicBlock, new_block: models.BasicBlock
) -> None:
    """Updates the phis of 'phi_block' with a new PhiArgument for 'new_block' with
    the same PhiArgument value as the 'inlined_block'"""
    for phi in phi_block.phis:
        existing_phi_arg = next((arg for arg in phi.args if arg.through == inlined_block), None)
        if existing_phi_arg is None:
            raise InternalError(
                f"Expected a single PhiArgument for {inlined_block} in {phi}",
                phi.source_location,
            )
        phi.args.append(PhiArgument(value=existing_phi_arg.value, through=new_block))
        attrs.validate(phi)
