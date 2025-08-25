import itertools
from collections.abc import Iterator

from puya import log
from puya.ir import models
from puya.utils import not_none

logger = log.get_logger(__name__)


def split_critical_edges(sub: models.Subroutine) -> None:
    id_counter: Iterator[int] | None = None
    blocks = []
    for predecessor in sub.body:
        blocks.append(predecessor)
        if len(predecessor.successors) <= 1:
            continue
        for successor in predecessor.successors:
            if len(successor.predecessors) <= 1:
                continue
            # edges between blocks with multiple successors to those with multiple predecessors
            # are critical edges, by splitting them here we can improve the destructured IR code
            if predecessor is successor:
                logger.debug(
                    f"not splitting critical edge with self loop in {predecessor}",
                    location=predecessor.source_location,
                )
            else:
                if id_counter is None:
                    # lazy compute of maximum ID
                    max_id = max(not_none(b.id) for b in sub.body)
                    id_counter = itertools.count(max_id + 1)
                new_block = _split_critical_edge(id_counter, predecessor, successor)
                blocks.append(new_block)
    sub.body[:] = blocks


def _split_critical_edge(
    id_counter: Iterator[int], predecessor: models.BasicBlock, successor: models.BasicBlock
) -> models.BasicBlock:
    logger.debug(f"splitting critical edge {predecessor}->{successor}")
    # create new block
    assert predecessor.terminator is not None
    new_block = models.BasicBlock(
        id=next(id_counter),
        label=f"split_critical_edge_from_{predecessor.id}_to_{successor.id}",
        terminator=models.Goto(
            target=successor,
            source_location=predecessor.terminator.source_location,
        ),
        source_location=predecessor.source_location,
    )

    # replace successor with new_block in terminator of predecessor,
    # and update successor's predecessors list + phi nodes
    new_block.add_predecessor(predecessor)
    predecessor.terminator.replace_target(find=successor, replace=new_block)
    successor.replace_predecessor(old=predecessor, new=new_block)
    return new_block
