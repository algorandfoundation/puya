from puya import log
from puya.ir import models
from puya.utils import StableSet, not_none

logger = log.get_logger(__name__)


def split_critical_edges(sub: models.Subroutine) -> None:
    edges_to_split = StableSet[tuple[models.BasicBlock, models.BasicBlock]]()
    for predecessor in sub.body:
        if len(predecessor.successors) <= 1:
            continue
        for successor in predecessor.successors:
            if len(successor.predecessors) > 1:
                # edge is critical
                edges_to_split.add((predecessor, successor))
    if not edges_to_split:
        return
    next_id = max(not_none(b.id) for b in sub.body) + 1
    split_blocks = dict[models.BasicBlock, list[models.BasicBlock]]()
    for predecessor, successor in edges_to_split:
        if predecessor is successor:
            logger.debug(
                f"not splitting critical edge with self loop in {predecessor}",
                location=predecessor.source_location,
            )
        else:
            # create new block
            assert predecessor.terminator is not None
            new_block = models.BasicBlock(
                id=next_id,
                label=f"split_critical_edge_from_{predecessor.id}_to_{successor.id}",
                terminator=models.Goto(
                    target=successor,
                    source_location=predecessor.terminator.source_location,
                ),
                predecessors=[predecessor],
                source_location=predecessor.source_location,
            )
            split_blocks.setdefault(predecessor, []).append(new_block)
            next_id += 1
            # replace successor with new_block in terminator of predecessor
            predecessor.terminator.replace_target(find=successor, replace=new_block)
            # update successor's predecessors list + phi nodes
            successor.predecessors.remove(predecessor)
            successor.predecessors.append(new_block)
            for phi in successor.phis:
                for phi_arg in phi.args:
                    if phi_arg.through is predecessor:
                        phi_arg.through = new_block
                        break
    blocks = []
    for block in sub.body:
        blocks.append(block)
        blocks.extend(split_blocks.get(block, []))
    sub.body = blocks
