from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

import structlog

from wyvern.awst import wtypes
from wyvern.awst.nodes import (
    AbiConstant,
    AbiDecode,
    AbiEncode,
    BytesEncoding,
    Expression,
    IndexExpression,
    IntrinsicCall,
    Literal,
    NewAbiArray,
    ReinterpretCast,
    UInt64Constant,
)
from wyvern.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    Iteration,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from wyvern.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.awst_build.utils import expect_operand_wtype, require_expression_builder
from wyvern.errors import CodeError, InternalError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from wyvern.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


def abi_to_avm_wtype(abi_wtype: wtypes.WType) -> wtypes.WType:
    match abi_wtype:
        case wtypes.abi_string_wtype:
            return wtypes.bytes_wtype
        case wtypes.AbiUIntN():
            return wtypes.uint64_wtype
        case _:
            raise InternalError("Invalid abi_wtype")


class AbiClassExpressionBuilder(BytesBackedClassExpressionBuilder, ABC):
    def __init__(
        self,
        location: SourceLocation,
    ):
        super().__init__(location)

    def member_access(
        self,
        name: str,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        """Handle self.name"""
        match name:
            case "encode":
                return AbiEncodeBuilder(location, self.produces())
            case _:
                return super().member_access(name, location)


class DynamicArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    element_abi_type: wtypes.WType | None
    abi_type: wtypes.AbiDynamicArray | None

    def __init__(
        self,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.element_abi_type = None
        self.abi_type = None

    def index(
        self,
        index: ExpressionBuilder | Literal,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match index:
            case TypeClassExpressionBuilder() as eb:
                self.element_abi_type = eb.produces()
                self.abi_type = wtypes.AbiDynamicArray.from_element_type(self.element_abi_type)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return self

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
            for a in args
        ]
        if self.element_abi_type is None:
            if non_literal_args:
                self.element_abi_type = non_literal_args[0].wtype
            else:
                raise CodeError(
                    "Empy arrays require a type annotation to be instantiated", location
                )
        if self.abi_type is None:
            self.abi_type = wtypes.AbiDynamicArray.from_element_type(self.element_abi_type)
        for a in non_literal_args:
            expect_operand_wtype(a, self.element_abi_type)

        array_expr = NewAbiArray(
            source_location=location, elements=tuple(non_literal_args), wtype=self.abi_type
        )
        return var_expression(array_expr)

    def produces(self) -> wtypes.WType:
        if not self.abi_type:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.abi_type


class StaticArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    element_abi_type: wtypes.WType | None
    abi_type: wtypes.AbiStaticArray | None
    array_size: int | None

    def __init__(
        self,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.element_abi_type = None
        self.abi_type = None

    def index_multiple(
        self,
        index: Sequence[ExpressionBuilder | Literal],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match index:
            case [TypeClassExpressionBuilder() as item_type, array_size]:
                match array_size:
                    case Literal(value=int(lit_value)):
                        self.array_size = lit_value
                    case ValueExpressionBuilder() as eb:
                        value = eb.rvalue()
                        if not isinstance(value, UInt64Constant):
                            raise CodeError("Array size must be compile time constant")
                        self.array_size = value.value
                    case _:
                        raise CodeError("Array size must be compile time constant")

                self.element_abi_type = item_type.produces()
                self.abi_type = wtypes.AbiStaticArray.from_element_type_and_size(
                    array_size=self.array_size,
                    element_type=self.element_abi_type,
                )

            case _:
                raise CodeError(
                    "Invalid type arguments for StaticArray. "
                    "Expected StaticArray[ItemType, typing.Literal[n]]",
                    location,
                )
        return self

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        non_literal_args = [
            require_expression_builder(a, msg="Array arguments must be non literals").rvalue()
            for a in args
        ]
        if self.element_abi_type is None:
            if non_literal_args:
                self.element_abi_type = non_literal_args[0].wtype
            else:
                raise CodeError(
                    "Empty arrays require a type annotation to be instantiated", location
                )
        if self.array_size is None:
            self.array_size = len(non_literal_args)
        elif self.array_size != len(non_literal_args):
            raise CodeError(
                f"StaticArray should be initialized with {self.array_size} values", location
            )

        if self.abi_type is None:
            self.abi_type = wtypes.AbiStaticArray.from_element_type_and_size(
                element_type=self.element_abi_type, array_size=self.array_size
            )
        for a in non_literal_args:
            expect_operand_wtype(a, self.element_abi_type)

        array_expr = NewAbiArray(
            source_location=location, elements=tuple(non_literal_args), wtype=self.abi_type
        )
        return var_expression(array_expr)

    def produces(self) -> wtypes.WType:
        if not self.abi_type:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.abi_type


class UIntNClassExpressionBuilder(AbiClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        if not self.abi_type:
            raise InternalError(
                "Cannot resolve wtype of generic EB until the index method is called with the "
                "generic type parameter."
            )
        return self.abi_type

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=int(int_literal), source_location=loc)]:
                const = AbiConstant(
                    value=int_literal.to_bytes(1, "big"),
                    source_location=loc,
                    wtype=self.abi_type,
                )
                return var_expression(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

    def index(
        self,
        index: ExpressionBuilder | Literal,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match index:
            case Literal(value=int(lit_value)):
                self.abi_type = wtypes.AbiUIntN.from_scale(lit_value)
            case ValueExpressionBuilder() as eb:
                value = eb.rvalue()
                if not isinstance(value, UInt64Constant):
                    raise CodeError("Array size must be compile time constant")
                self.abi_type = wtypes.AbiUIntN.from_scale(value.value)
            case _:
                raise CodeError("Array size must be compile time constant")
        return self


class StringClassExpressionBuilder(AbiClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return self.abi_type

    def __init__(self, location: SourceLocation):
        super().__init__(
            location,
        )
        self.abi_type = wtypes.abi_string_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes(bytes_val), source_location=loc)]:
                bytes_const = len(bytes_val).to_bytes(2, "big") + bytes_val
                const = AbiConstant(
                    value=bytes_const,
                    source_location=loc,
                    wtype=wtypes.abi_string_wtype,
                    bytes_encoding=BytesEncoding.utf8,
                )
                return var_expression(const)
            case [Literal(value=str(str_val), source_location=loc)]:
                # TODO: Confirm encoding
                bytes_val = str_val.encode("utf8")
                bytes_const = len(bytes_val).to_bytes(2, "big") + bytes_val

                const = AbiConstant(
                    value=bytes_const,
                    source_location=loc,
                    wtype=wtypes.abi_string_wtype,
                    bytes_encoding=BytesEncoding.utf8,
                )
                return var_expression(const)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class AbiEncodeBuilder(IntermediateExpressionBuilder):
    def __init__(self, location: SourceLocation, abi_type: wtypes.WType):
        super().__init__(location=location)
        self.abi_type = abi_type

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb] if eb.rvalue().wtype == abi_to_avm_wtype(
                self.abi_type
            ):
                value = eb.rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

        expr = AbiEncode(
            source_location=location,
            value=value,
            wtype=self.abi_type,
        )
        return var_expression(expr)


class AbiDecodeBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location=location)
        match expr.wtype:
            case wtypes.abi_string_wtype:
                pass
            case wtypes.AbiUIntN():
                pass
            case _:
                raise InternalError("Unsupported wtype")
        self.expr = expr

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case []:
                pass
            case _:
                raise CodeError("Invalid/unhandled arguments", location)

        expr = AbiDecode(
            source_location=location, value=self.expr, wtype=abi_to_avm_wtype(self.expr.wtype)
        )
        return var_expression(expr)


class AbiEncodedExpressionBuilder(ValueExpressionBuilder):
    def member_access(
        self,
        name: str,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match name:
            case "decode":
                return AbiDecodeBuilder(self.expr, location)
            case "bytes":
                return var_expression(
                    ReinterpretCast(
                        expr=self.expr,
                        wtype=wtypes.bytes_wtype,
                        source_location=location,
                    )
                )
            case _:
                raise CodeError(
                    f"Unrecognised member of bytes: {name}",
                    location,
                )


class StringExpressionBuilder(AbiEncodedExpressionBuilder):
    wtype = wtypes.abi_string_wtype

    def member_access(
        self,
        name: str,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match name:
            case _:
                return super().member_access(name, location)


class UIntNExpressionBuilder(AbiEncodedExpressionBuilder):
    def __init__(self, expr: Expression):
        self.wtype = expr.wtype
        super().__init__(expr)

    def member_access(
        self,
        name: str,
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match name:
            case _:
                return super().member_access(name, location)


class AbiArrayExpressionBuilder(ValueExpressionBuilder, ABC):
    wtype: wtypes.AbiDynamicArray | wtypes.AbiStaticArray

    def iterate(self) -> Iteration:
        return self.rvalue()

    def index(
        self, index: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        index_expr = expect_operand_wtype(index, wtypes.uint64_wtype)
        expr = IndexExpression(
            source_location=location,
            base=self.expr,
            index=index_expr,
            wtype=self.wtype.element_type,
        )
        return var_expression(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "bytes":
                return var_expression(
                    ReinterpretCast(
                        expr=self.expr,
                        wtype=wtypes.bytes_wtype,
                        source_location=location,
                    )
                )
            case _:
                return super().member_access(name, location)


class DynamicArrayExpressionBuilder(AbiArrayExpressionBuilder):
    wtype: wtypes.AbiDynamicArray

    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.AbiDynamicArray)
        self.wtype = expr.wtype
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


class StaticArrayExpressionBuilder(ValueExpressionBuilder):
    wtype: wtypes.AbiStaticArray

    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.AbiStaticArray)
        self.wtype = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case "length":
                return var_expression(
                    UInt64Constant(value=self.wtype.array_size, source_location=location)
                )
            case _:
                return super().member_access(name, location)
