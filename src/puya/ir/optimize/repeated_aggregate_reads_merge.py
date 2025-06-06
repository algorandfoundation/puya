import typing

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.visitor import IRTraverser

logger = log.get_logger(__name__)


def merge_chained_aggregate_reads(_: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False

    reads = _AggregateReadsCollector.collect(subroutine)
    for ass, read in reads.values():
        merged_read = read
        while base_read_ass := reads.get(merged_read.base):
            base_read = base_read_ass.read
            merged_read = attrs.evolve(
                base_read, indexes=[*base_read.indexes, *merged_read.indexes]
            )

        if merged_read != read:
            modified = True
            logger.debug(f"replacing {read!s} with {merged_read!s}", location=ass.source_location)
            ass.source = merged_read

    return modified


class _AggregateRead(typing.NamedTuple):
    ass: models.Assignment
    read: models.AggregateReadIndex


@attrs.define(kw_only=True)
class _AggregateReadsCollector(IRTraverser):
    reads: dict[models.Value, _AggregateRead] = attrs.field(factory=dict)

    @classmethod
    def collect(cls, sub: models.Subroutine) -> dict[models.Value, _AggregateRead]:
        collector = cls()
        collector.visit_all_blocks(sub.body)
        return collector.reads

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        if isinstance(ass.source, models.AggregateReadIndex):
            (target,) = ass.targets
            self.reads[target] = _AggregateRead(ass, ass.source)
