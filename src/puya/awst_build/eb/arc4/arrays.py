from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4ArrayEncode,
    Expression,
    IndexExpression,
    IntrinsicCall,
    Literal,
    UInt64BinaryOperation,
    UInt64BinaryOperator,
    UInt64Constant,
)
from puya.awst_build.eb.arc4.base import (
    get_bytes_expr_builder,
    get_integer_literal_value,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
    require_expression_builder,
)
from puya.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class DynamicArrayGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        match index:
            case [TypeClassExpressionBuilder() as eb]:
                element_wtype = eb.produces()
                wtype = wtypes.ARC4DynamicArray.from_element_type(element_wtype)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return DynamicArrayClassExpressionBuilder(location=location, wtype=wtype)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return dynamic_array_constructor(args=args, wtype=None, location=location)


def dynamic_array_constructor(
    args: Sequence[ExpressionBuilder | Literal],
    wtype: wtypes.ARC4DynamicArray | None,
    location: SourceLocation,
) -> ExpressionBuilder:
    non_literal_args = [
        require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
        for a in args
    ]
    if wtype is None:
        if non_literal_args:
            element_wtype = non_literal_args[0].wtype
            wtype = wtypes.ARC4DynamicArray.from_element_type(element_wtype)
        else:
            raise CodeError("Empy arrays require a type annotation to be instantiated", location)

    for a in non_literal_args:
        expect_operand_wtype(a, wtype.element_type)

    return var_expression(
        ARC4ArrayEncode(
            source_location=location,
            values=tuple(non_literal_args),
            wtype=wtype,
        )
    )


class DynamicArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.ARC4DynamicArray | None = None):
        super().__init__(location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return dynamic_array_constructor(args=args, wtype=self.wtype, location=location)

    def produces(self) -> wtypes.WType:
        if not self.wtype:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.wtype


class StaticArrayGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        match index:
            case [TypeClassExpressionBuilder() as item_type, array_size]:
                array_size_ = get_integer_literal_value(array_size, "Array size")
                element_wtype = item_type.produces()
                wtype = wtypes.ARC4StaticArray.from_element_type_and_size(
                    array_size=array_size_,
                    element_type=element_wtype,
                )

            case _:
                raise CodeError(
                    "Invalid type arguments for StaticArray. "
                    "Expected StaticArray[ItemType, typing.Literal[n]]",
                    location,
                )
        return StaticArrayClassExpressionBuilder(location=location, wtype=wtype)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return static_array_constructor(args=args, wtype=None, location=location)


def static_array_constructor(
    args: Sequence[ExpressionBuilder | Literal],
    wtype: wtypes.ARC4StaticArray | None,
    location: SourceLocation,
) -> ExpressionBuilder:
    non_literal_args = [
        require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
        for a in args
    ]
    if wtype is None:
        if non_literal_args:
            element_wtype = non_literal_args[0].wtype
            array_size = len(non_literal_args)
            wtype = wtypes.ARC4StaticArray.from_element_type_and_size(
                array_size=array_size,
                element_type=element_wtype,
            )
        else:
            raise CodeError("Empty arrays require a type annotation to be instantiated", location)
    elif wtype.array_size != len(non_literal_args):
        raise CodeError(
            f"StaticArray should be initialized with {wtype.array_size} values",
            location,
        )

    for a in non_literal_args:
        expect_operand_wtype(a, wtype.element_type)

    return var_expression(
        ARC4ArrayEncode(
            source_location=location,
            values=tuple(non_literal_args),
            wtype=wtype,
        )
    )


class StaticArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def __init__(self, location: SourceLocation, wtype: wtypes.ARC4StaticArray | None = None):
        super().__init__(location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        return static_array_constructor(args=args, wtype=self.wtype, location=location)

    def produces(self) -> wtypes.WType:
        if not self.wtype:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.wtype


class AddressClassExpressionBuilder(StaticArrayClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(location=location)
        element_wtype = wtypes.ARC4UIntN.from_scale(8, alias="byte")
        array_size = 32
        self.wtype = wtypes.ARC4StaticArray.from_element_type_and_size(
            element_wtype, array_size=array_size, alias="address"
        )

    def index_multiple(
        self, index: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(
            "Address does not support type arguments",
            location,
        )


class ARC4ArrayExpressionBuilder(ValueExpressionBuilder, ABC):
    wtype: wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray

    def iterate(self) -> Iteration:
        return self.rvalue()

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        if isinstance(index, Literal) and isinstance(index.value, int) and index.value < 0:
            index_expr: Expression = UInt64BinaryOperation(
                left=expect_operand_wtype(
                    self.member_access("length", index.source_location), wtypes.uint64_wtype
                ),
                op=UInt64BinaryOperator.sub,
                right=UInt64Constant(
                    value=abs(index.value), source_location=index.source_location
                ),
                source_location=index.source_location,
            )
        else:
            index_expr = expect_operand_wtype(index, wtypes.uint64_wtype)
        return var_expression(
            IndexExpression(
                source_location=location,
                base=self.expr,
                index=index_expr,
                wtype=self.wtype.element_type,
            )
        )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)


class DynamicArrayExpressionBuilder(ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4DynamicArray)
        self.wtype: wtypes.ARC4DynamicArray = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return var_expression(
                    IntrinsicCall(
                        op_code="extract_uint16",
                        stack_args=[self.expr, UInt64Constant(value=0, source_location=location)],
                        source_location=location,
                        wtype=wtypes.uint64_wtype,
                    )
                )
            case _:
                return super().member_access(name, location)


class StaticArrayExpressionBuilder(ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4StaticArray)
        self.wtype: wtypes.ARC4StaticArray = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return var_expression(
                    UInt64Constant(value=self.wtype.array_size, source_location=location)
                )
            case _:
                return super().member_access(name, location)
