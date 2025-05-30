import abc
import typing
from abc import ABC

from puya import log
from puya.awst.nodes import (
    Expression,
    IndexExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import InstanceExpressionBuilder
from puyapy.awst_build.eb._utils import (
    CopyBuilder,
    cast_to_bytes,
    compare_bytes,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder

logger = log.get_logger(__name__)


class _ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType], ABC):
    @typing.override
    def iterate(self) -> Expression:
        if not self.pytype.items_wtype.immutable:
            # this case is an error raised during AWST validation
            # adding a front end specific message here to compliment the error message
            # raise across all front ends
            logger.info(
                "use `algopy.urange(<array>.length)` to iterate by index",
                location=self.source_location,
            )
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self.pytype.items

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        array_length = self.length(index.source_location)
        index = resolve_negative_literal_index(index, array_length, location)
        result_expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            wtype=self.pytype.items_wtype,
            source_location=location,
        )
        return builder_for_instance(self.pytype.items, result_expr)

    @abc.abstractmethod
    def length(self, location: SourceLocation) -> InstanceBuilder: ...

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return self.length(location)
            case "copy":
                return CopyBuilder(self.resolve(), location, self.pytype)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(self=self, op=op, other=other, source_location=location)

    @typing.override
    @typing.final
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        logger.error("item containment with arrays is currently unsupported", location=location)
        return dummy_value(pytypes.BoolType, location)

    @typing.override
    @typing.final
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing arrays is currently unsupported", location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return cast_to_bytes(self.resolve(), location)  # TODO: method coverage
