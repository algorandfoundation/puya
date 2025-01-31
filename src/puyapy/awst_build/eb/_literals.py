import typing

from puya import log
from puya.awst.nodes import (
    BinaryBooleanOperator,
    BoolConstant,
    BytesConstant,
    BytesEncoding,
    Expression,
    Lvalue,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build import intrinsic_factory, pytypes
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    LiteralBuilder,
    TypeBuilder,
)
from puyapy.awst_build.utils import fold_binary_expr, fold_unary_expr
from puyapy.models import ConstantValue

logger = log.get_logger(__name__)


class LiteralBuilderImpl(LiteralBuilder):
    def __init__(self, value: ConstantValue, source_location: SourceLocation):
        super().__init__(source_location)
        self._value = value
        match value:
            case bool():
                typ: pytypes.PyType = pytypes.BoolType
            case int():
                typ = pytypes.IntLiteralType
            case str():
                typ = pytypes.StrLiteralType
            case bytes():
                typ = pytypes.BytesLiteralType
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
    def resolve(self) -> Expression:
        if isinstance(self.value, bool):
            return BoolConstant(value=self.value, source_location=self.source_location)
        raise CodeError("a Python literal is not valid at this location", self.source_location)

    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return converter.convert_literal(literal=self, location=converter.source_location)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder | None:
        return converter.try_convert_literal(literal=self, location=converter.source_location)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        raise CodeError("cannot assign to literal", self.source_location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        match self.value:
            case str(str_value):
                return BytesConstant(
                    value=str_value.encode(), encoding=BytesEncoding.utf8, source_location=location
                )
            case bytes(bytes_value):
                return BytesConstant(
                    value=bytes_value, encoding=BytesEncoding.unknown, source_location=location
                )
            case bool():
                return intrinsic_factory.itob(self.resolve(), location)
        raise CodeError(f"cannot serialize literal of type {self.pytype}", location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        raise CodeError("cannot delete literal", location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> LiteralBuilder:
        folded = fold_unary_expr(location, op.value, self.value)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> LiteralBuilder:
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
    ) -> LiteralBuilder:
        if not isinstance(other, LiteralBuilder):
            return NotImplemented
        lhs, rhs = self.value, other.value
        if reverse:
            lhs, rhs = rhs, lhs
        folded = fold_binary_expr(location, op.value, lhs, rhs)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        if not isinstance(other, LiteralBuilder):
            return super().bool_binary_op(other, op, location)
        folded = fold_binary_expr(location, op.value, self.value, other.value)
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        raise CodeError("cannot assign to literal", location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> LiteralBuilder:
        if not isinstance(item, LiteralBuilder):
            raise CodeError("cannot perform containment check with non-constant value", location)
        try:
            folded = item.value in self.value  # type: ignore[operator]
        except Exception as ex:
            raise CodeError(str(ex), location) from ex
        return LiteralBuilderImpl(value=folded, source_location=location)

    @typing.override
    def iterate(self) -> typing.Never:
        raise CodeError("cannot iterate literal")

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> LiteralBuilder:
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
    ) -> LiteralBuilder:
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
    def member_access(self, name: str, location: SourceLocation) -> LiteralBuilder:
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
        return LiteralBuilderImpl(value=value, source_location=location)

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        return self
