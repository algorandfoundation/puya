import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import IntrinsicCall, SizeOf
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,  # TODO: file coverage and remove this comma
)

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
                if not _is_bytes_encoded(typ):
                    logger.error(
                        "argument must be a bytes encoded type reference", location=location
                    )
                    return dummy_value(typ, location)
            case _:
                raise CodeError(
                    "argument must be a bytes encoded type reference", location=location
                )
        wtype = typ.checked_wtype(location)
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


def _is_bytes_encoded(typ: pytypes.PyType) -> bool:
    if typ <= pytypes.UInt64Type:
        return False
    wtype = typ.wtype
    if isinstance(wtype, str):
        return False
    return wtype.persistable
