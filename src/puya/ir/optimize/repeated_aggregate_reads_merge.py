import typing

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import (
    models,
    types_ as types,
)
from puya.ir.visitor import IRTraverser
from puya.parse import sequential_source_locations_merge

logger = log.get_logger(__name__)


def merge_chained_aggregate_reads(_: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False

    collector = _AggregateReadsCollector.collect(subroutine)
    for ass, read in collector.reads.values():
        merged_read = read
        while base_read_ass := collector.get_read(merged_read.base):
            base_read = base_read_ass.read
            merged_source_location = sequential_source_locations_merge(
                (merged_read.source_location, base_read.source_location)
            )
            merged_read = models.ExtractValue(
                base=base_read.base,
                base_type=base_read.base_type,
                indexes=[*base_read.indexes, *merged_read.indexes],
                ir_type=merged_read.ir_type,
                check_bounds=base_read.check_bounds or merged_read.check_bounds,
                source_location=merged_source_location,
            )

        if merged_read is not read:
            modified = True
            logger.debug(f"replacing {read!s} with {merged_read!s}", location=ass.source_location)
            ass.source = merged_read

    return modified


class _AggregateRead(typing.NamedTuple):
    ass: models.Assignment
    read: models.ExtractValue


@attrs.define(kw_only=True)
class _AggregateReadsCollector(IRTraverser):
    reads: dict[models.Value, _AggregateRead] = attrs.field(factory=dict)
    decodes: dict[models.Value, models.Value] = attrs.field(factory=dict)

    def get_read(self, value: models.Value) -> _AggregateRead | None:
        while True:
            try:
                value = self.decodes[value]
            except KeyError:
                break
        return self.reads.get(value)

    @classmethod
    def collect(cls, sub: models.Subroutine) -> typing.Self:
        collector = cls()
        collector.visit_all_blocks(sub.body)
        return collector

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        if isinstance(ass.source, models.ExtractValue):
            (target,) = ass.targets
            self.reads[target] = _AggregateRead(ass, ass.source)
        elif isinstance(ass.source, models.DecodeBytes):
            if types.EncodedType(ass.source.encoding) == ass.source.ir_type:
                (target,) = ass.targets
                self.decodes[target] = ass.source.value
