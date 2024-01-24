import structlog

from puya.avm_type import AVMType
from puya.context import CompileContext
from puya.ir import models
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
                for target in unique(terminator.targets()):
                    if target is not goto:
                        remove_target(block, target)
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
