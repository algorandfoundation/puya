import attrs

from puya import log
from puya.avm import AVMType
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import get_definition
from puya.ir.ssa import TrivialPhiRemover
from puya.ir.types_ import PrimitiveIRType
from puya.utils import unique

logger = log.get_logger(__name__)


# the ratio of default cases to all cases when a match of constant values
# can be simplified to a goto-nth
_SWITCH_SPARSENESS_SIMPLIFICATION_RATIO = 0.5


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
            case models.ProgramExit(result=models.UInt64Constant(value=0)):
                logger.debug("simplifying exit 0 to err")
                block.terminator = models.Fail(
                    source_location=terminator.source_location, error_message=None
                )
            case models.ConditionalBranch(
                condition=models.UInt64Constant(value=value), zero=zero, non_zero=non_zero
            ):
                logger.debug("simplifying conditional branch with a constant into a goto")
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
                    phis=[], ops=[], terminator=models.Fail(error_message=fail_comment)
                ) as err_block,
                non_zero=non_zero,
                source_location=source_location,
            ):
                logger.debug("inlining condition branch to err block into an assert true")
                block.ops.append(
                    models.Intrinsic(
                        op=AVMOp.assert_,
                        args=[condition],
                        error_message=fail_comment,
                        source_location=source_location,
                    )
                )
                block.terminator = models.Goto(target=non_zero, source_location=source_location)
                if err_block not in block.successors:
                    remove_target(block, err_block)
            case models.ConditionalBranch(
                condition=models.Register() as condition,
                non_zero=models.BasicBlock(
                    phis=[], ops=[], terminator=models.Fail(error_message=fail_comment)
                ) as err_block,
                zero=zero,
                source_location=source_location,
            ):
                logger.debug("inlining condition branch to err block into an assert false")
                not_condition = models.Register(
                    name=f"not%{condition.name}",
                    ir_type=PrimitiveIRType.bool,
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
                        error_message=fail_comment,
                        source_location=source_location,
                    )
                )
                block.terminator = models.Goto(target=zero, source_location=source_location)
                if err_block not in block.successors:
                    remove_target(block, err_block)
            case (
                models.ConditionalBranch(
                    condition=models.Register() as condition,
                ) as branch
            ) if (
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
            case (
                models.Switch(
                    value=models.Value(atype=AVMType.uint64) as value,
                    cases=cases,
                    default=default_block,
                    source_location=source_location,
                ) as switch
            ) if _can_simplify_switch(switch):
                logger.debug("simplifying a switch with constants into goto nth")
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
                logger.debug("simplifying a goto nth with a constant into a goto")
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
                default=non_zero,
            ):  # reduces to ConditionalBranch
                logger.debug("simplifying a goto nth with two targets into a conditional branch")
                block.terminator = models.ConditionalBranch(
                    condition=value,
                    zero=zero,
                    non_zero=non_zero,
                    source_location=terminator.source_location,
                )
            case _:
                continue
        changes = True
        logger.debug(f"simplified terminator of {block} from {terminator} to {block.terminator}")
    for phi in modified_phis:
        TrivialPhiRemover.try_remove(phi, subroutine.body)
    return changes


def _can_simplify_switch(switch: models.Switch) -> bool:
    total_targets = 0
    for case in switch.cases:
        if not isinstance(case, models.UInt64Constant):
            return False
        total_targets = max(total_targets, case.value)
    default_targets = total_targets - len(switch.cases)
    return default_targets < (total_targets * _SWITCH_SPARSENESS_SIMPLIFICATION_RATIO)
