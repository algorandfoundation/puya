import abc
import typing
from collections.abc import Sequence

import typing_extensions

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import ARC4FromBytes, Expression
from puya.errors import InternalError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, InstanceExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder

logger = log.get_logger(__name__)
_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class ValidatableInstanceExpressionBuilder(InstanceExpressionBuilder[_TPyType_co], abc.ABC):
    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "validate":
            return ValidateEncoding(self.resolve(), validate_type=self.pytype, location=location)
        else:
            return super().member_access(name, location)


class ValidateEncoding(FunctionBuilder):
    def __init__(self, expr: Expression, validate_type: pytypes.PyType, location: SourceLocation):
        super().__init__(location)
        self.validate_type = validate_type
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        wtype = self.validate_type.checked_wtype(location)
        if not isinstance(wtype, wtypes.ARC4Type | wtypes.StackArray):
            raise InternalError("can only validate ARC4 encodable types", location=location)
        from_bytes = ARC4FromBytes(
            value=self.expr,
            validate=True,
            wtype=wtype,
            source_location=location,
        )
        return builder_for_instance(self.validate_type, from_bytes)
