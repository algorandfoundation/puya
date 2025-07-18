import typing
from collections.abc import Sequence

from puya import log
from puya.avm import AVMType
from puya.awst.nodes import IntrinsicCall, SizeOf
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder

logger = log.get_logger(__name__)


class ZeroBytesBuilder(FunctionBuilder):
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
                wtype = typ.checked_wtype(location)
                if (wtype.scalar_type is AVMType.uint64) or not wtype.persistable:
                    logger.error(
                        "argument must be a bytes encoded type reference", location=location
                    )
                    return dummy_value(typ, location)
            case _:
                raise CodeError(
                    "argument must be a bytes encoded type reference", location=location
                )

        return builder_for_instance(
            typ,
            IntrinsicCall(
                op_code="bzero",
                stack_args=[
                    SizeOf(
                        size_wtype=wtype,
                        source_location=location,
                    )
                ],
                wtype=wtype,
                source_location=location,
            ),
        )
