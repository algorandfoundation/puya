import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import SizeOf
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class SizeOfBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [NodeBuilder(pytype=pytypes.TypeType(typ=typ))]:
                pass
            case [InstanceBuilder(pytype=typ)]:
                pass
            case _:
                logger.error("argument must be a type reference or expression", location=location)
                return dummy_value(pytypes.UInt64Type, location)
        size_of = SizeOf(
            size_wtype=typ.checked_wtype(location),
            source_location=location,
        )
        return UInt64ExpressionBuilder(size_of)
