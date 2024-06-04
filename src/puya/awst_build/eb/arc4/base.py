from __future__ import annotations

import abc
import typing

import typing_extensions

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    CheckedMaybe,
    Copy,
    Expression,
    ReinterpretCast,
    SingleEvaluation,
    TupleExpression,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
)
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb._utils import compare_expr_bytes
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderComparisonOp,
    InstanceBuilder,
    NodeBuilder,
)
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class ARC4TypeBuilder(BytesBackedTypeBuilder[_TPyType_co], abc.ABC):
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "from_log":
                return ARC4FromLogBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


class ARC4FromLogBuilder(FunctionBuilder):
    def __init__(self, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location=location)
        self.typ = typ

    @classmethod
    def abi_expr_from_log(
        cls, typ: pytypes.PyType, value: Expression, location: SourceLocation
    ) -> Expression:
        tmp_value = SingleEvaluation(value)
        arc4_value = intrinsic_factory.extract(tmp_value, start=4, loc=location)
        arc4_prefix = intrinsic_factory.extract(tmp_value, start=0, length=4, loc=location)
        arc4_prefix_is_valid = compare_expr_bytes(
            lhs=arc4_prefix,
            rhs=BytesConstant(
                value=b"\x15\x1f\x7c\x75",
                source_location=location,
                encoding=BytesEncoding.base16,
            ),
            op=BuilderComparisonOp.eq,
            source_location=location,
        )
        checked_arc4_value = CheckedMaybe(
            expr=TupleExpression(
                items=(arc4_value, arc4_prefix_is_valid.resolve()),
                wtype=wtypes.WTuple((arc4_value.wtype, wtypes.bool_wtype), location),
                source_location=location,
            ),
            comment="ARC4 prefix is valid",
        )
        return ReinterpretCast(
            expr=checked_arc4_value,
            wtype=typ.wtype,
            source_location=location,
        )

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder() as eb]:
                result_expr = self.abi_expr_from_log(self.typ, eb.resolve(), location)
                return builder_for_instance(self.typ, result_expr)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class CopyBuilder(FunctionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation, typ: pytypes.PyType):
        self._typ = typ
        super().__init__(location)
        self.expr = expr

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                expr_result = Copy(
                    value=self.expr, wtype=self.expr.wtype, source_location=location
                )
                return builder_for_instance(self._typ, expr_result)
        raise CodeError("Invalid/Unexpected arguments", location)


def arc4_bool_bytes(
    builder: InstanceBuilder, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> InstanceBuilder:
    false_value = ReinterpretCast(
        expr=BytesConstant(
            value=false_bytes,
            encoding=BytesEncoding.base16,
            source_location=location,
        ),
        wtype=builder.pytype.wtype,
        source_location=location,
    )
    return compare_expr_bytes(
        op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
        lhs=builder.resolve(),
        rhs=false_value,
        source_location=location,
    )
