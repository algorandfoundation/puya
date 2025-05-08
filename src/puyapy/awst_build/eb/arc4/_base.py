import abc
import typing
from abc import ABC
from collections.abc import Sequence

import typing_extensions

from puya import log
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    CheckedMaybe,
    Copy,
    Expression,
    IndexExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puyapy.awst_build.eb._utils import (
    compare_bytes,
    compare_expr_bytes,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import BuilderComparisonOp, InstanceBuilder, NodeBuilder

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
        cls, typ: pytypes.PyType, value: InstanceBuilder, location: SourceLocation
    ) -> Expression:
        tmp_value = value.single_eval().resolve()
        arc4_value = intrinsic_factory.extract(
            tmp_value, start=4, loc=location, result_type=typ.checked_wtype(location)
        )
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
        return CheckedMaybe.from_tuple_items(
            expr=arc4_value,
            check=arc4_prefix_is_valid.resolve(),
            source_location=location,
            comment="application log value is not the result of an ABI return",
        )

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, pytypes.BytesType, location)
        result_expr = self.abi_expr_from_log(self.typ, arg, location)
        return builder_for_instance(self.typ, result_expr)


class CopyBuilder(FunctionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation, typ: pytypes.PyType):
        super().__init__(location)
        self._typ = typ
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
        expr_result = Copy(value=self.expr, source_location=location)
        return builder_for_instance(self._typ, expr_result)


def arc4_bool_bytes(
    builder: InstanceBuilder, false_bytes: bytes, location: SourceLocation, *, negate: bool
) -> InstanceBuilder:
    lhs = builder.resolve()
    false_value = BytesConstant(
        value=false_bytes,
        encoding=BytesEncoding.base16,
        wtype=lhs.wtype,
        source_location=location,
    )
    return compare_expr_bytes(
        op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
        lhs=lhs,
        rhs=false_value,
        source_location=location,
    )


class _ARC4ArrayExpressionBuilder(BytesBackedInstanceExpressionBuilder[pytypes.ArrayType], ABC):
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
        logger.error(
            "item containment with ARC-4 arrays is currently unsupported", location=location
        )
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
        raise CodeError("slicing ARC-4 arrays is currently unsupported", location)
