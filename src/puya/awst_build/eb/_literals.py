import typing

from puya import log
from puya.awst.nodes import BoolConstant, ConstantValue, Expression, Lvalue, Statement
from puya.awst_build import pytypes
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    NodeBuilder,
)
from puya.awst_build.utils import fold_binary_expr, fold_unary_expr
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

class LiteralBuilderImpl(LiteralBuilder):

    def __init__(self, value: ConstantValue, source_location: SourceLocation):
        super().__init__(source_location)
        self._value = value
        match value:
            case int():
                typ = pytypes.IntLiteralType
            case str():
                typ = pytypes.StrLiteralType
            case bytes():
                typ = pytypes.BytesLiteralType
            case bool():
                typ = pytypes.BoolType
            case _:
                typing.assert_never(value)
        self._pytype = typ

    @property
    def value(self) -> ConstantValue:
        return self._value

    @property
    @typing.override
    def pytype(self) -> pytypes.PyType:
        return self._pytype

    @typing.override
    def rvalue(self) -> Expression:
        # TODO: can we somehow trap this to only be as final act of assignment?
        raise CodeError("A Python literal is not valid at this location")

    @typing.override
    def lvalue(self) -> Lvalue:
        raise CodeError("cannot assign to literal")

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError("cannot delete literal", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        folded = fold_unary_expr(location, op.value, self.value)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        if not isinstance(other, LiteralBuilder):
            return NotImplemented
        folded = fold_binary_expr(location, op.value, self.value, other.value)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        if not isinstance(other, LiteralBuilder):
            return NotImplemented
        lhs, rhs = self.value, other.value
        if reverse:
            lhs, rhs = rhs, lhs
        folded = fold_binary_expr(location, op.value, lhs, rhs)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("cannot assign to literal", location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if not isinstance(item, LiteralBuilder):
            raise CodeError("cannot perform substring check with non-constant value", location)
        try:
            folded = item.value in self.value  # type: ignore[operator]
        except Exception as ex:
            raise CodeError(str(ex), location) from ex
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def iterate(self) -> Iteration:
        raise CodeError("cannot iterate literal")

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if not isinstance(index, LiteralBuilder):
            raise CodeError("cannot index literal with non-constant value", location)
        try:
            folded = self.value[index.value]  # type: ignore[index]
        except Exception as ex:
            raise CodeError(str(ex), location) from ex
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        def _constant_slice_arg(index: InstanceBuilder | None) -> ConstantValue | None:
            if index is None:
                return None
            if not isinstance(index, LiteralBuilder):
                raise CodeError("cannot slice literal with non-constant value", location)
            return index.value

        begin = _constant_slice_arg(begin_index)
        end = _constant_slice_arg(end_index)
        stride_ = _constant_slice_arg(stride)
        try:
            folded = self.value[begin:end:stride_]  # type: ignore[index,misc]
        except Exception as ex:
            raise CodeError(str(ex), location) from ex
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        # TODO: support stuff like int.from_bytes etc
        raise CodeError("unsupported member access from literal", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        if isinstance(self.value, bool):
            value = self.value
            warn = False
        else:
            value = bool(self.value)
            warn = True
        if negate:
            value = not value
        if warn:
            logger.warning(f"expression is always {value}", location=location)
        const = BoolConstant(value=value, source_location=location)
        return BoolExpressionBuilder(const)
