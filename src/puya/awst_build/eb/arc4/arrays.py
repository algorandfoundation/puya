from __future__ import annotations

import typing
from abc import ABC

from puya import log
from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    ARC4ArrayEncode,
    ArrayConcat,
    ArrayExtend,
    ArrayPop,
    BytesComparisonExpression,
    CheckedMaybe,
    EqualityComparison,
    Expression,
    ExpressionStatement,
    IndexExpression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    SingleEvaluation,
    Statement,
    TupleExpression,
    UInt64BinaryOperation,
    UInt64BinaryOperator,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.arc4._utils import expect_arc4_operand_wtype
from puya.awst_build.eb.arc4.base import (
    CopyBuilder,
    arc4_bool_bytes,
    arc4_compare_bytes,
    get_bytes_expr,
    get_bytes_expr_builder,
    get_integer_literal_value,
)
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    GenericClassExpressionBuilder,
    IntermediateExpressionBuilder,
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

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class DynamicArrayGenericClassExpressionBuilder(GenericClassExpressionBuilder):
    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        match indexes:
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
            raise CodeError("Empty arrays require a type annotation to be instantiated", location)

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
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> TypeClassExpressionBuilder:
        match indexes:
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
    def __init__(self, location: SourceLocation, wtype: wtypes.ARC4StaticArray):
        super().__init__(location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
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
        super().__init__(location=location, wtype=wtypes.arc4_address_type)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                const_op = intrinsic_factory.zero_address(location, as_type=self.wtype)
                return var_expression(const_op)
            case [ExpressionBuilder(value_type=wtypes.account_wtype) as eb]:
                address_bytes: Expression = get_bytes_expr(eb.rvalue())
            case [Literal(value=str(addr_value))]:
                if not wtypes.valid_address(addr_value):
                    raise CodeError(
                        f"Invalid address value. Address literals should be"
                        f" {ENCODED_ADDRESS_LENGTH} characters and not include base32 padding",
                        location,
                    )
                address_bytes = AddressConstant(value=addr_value, source_location=location)
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                value = eb.rvalue()
                address_bytes_temp = SingleEvaluation(value)
                is_correct_length = NumericComparisonExpression(
                    operator=NumericComparison.eq,
                    source_location=location,
                    lhs=UInt64Constant(value=32, source_location=location),
                    rhs=intrinsic_factory.bytes_len(address_bytes_temp, location),
                )
                address_bytes = CheckedMaybe.from_tuple_items(
                    expr=address_bytes_temp,
                    check=is_correct_length,
                    source_location=location,
                    comment="Address length is 32 bytes",
                )
            case _:
                raise CodeError(
                    "Address constructor expects a single argument of type"
                    f" {wtypes.account_wtype} or {wtypes.bytes_wtype}, or a string literal",
                    location=location,
                )
        assert self.wtype, "wtype should not be None"
        return var_expression(
            ReinterpretCast(expr=address_bytes, wtype=self.wtype, source_location=location)
        )

    def index_multiple(
        self, indexes: Sequence[ExpressionBuilder | Literal], location: SourceLocation
    ) -> ExpressionBuilder:
        raise CodeError(
            "Address does not support type arguments",
            location,
        )


class ARC4ArrayExpressionBuilder(ValueExpressionBuilder, ABC):
    wtype: wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray

    def iterate(self) -> Iteration:
        if not self.wtype.element_type.immutable:
            logger.error(
                "Cannot directly iterate an ARC4 array of mutable objects,"
                " construct a for-loop over the indexes via urange(<array>.length) instead",
                location=self.source_location,
            )
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
            case "copy":
                return CopyBuilder(self.expr, location)
            case _:
                return super().member_access(name, location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return arc4_compare_bytes(self, op, other, location)


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
            case "append":
                return AppendExpressionBuilder(self.expr, location)
            case "extend":
                return ExtendExpressionBuilder(self.expr, location)
            case "pop":
                return PopExpressionBuilder(self.expr, location)
            case _:
                return super().member_access(name, location)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return ExpressionStatement(
                    expr=ArrayExtend(
                        base=self.expr,
                        other=match_array_concat_arg(
                            (rhs,),
                            self.wtype.element_type,
                            source_location=location,
                            msg="Array concat expects array or tuple of the same element type. "
                            f"Element type: {self.wtype.element_type}",
                        ),
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
                    )
                )
            case _:
                return super().augmented_assignment(op, rhs, location)

    def binary_op(
        self,
        other: ExpressionBuilder | Literal,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> ExpressionBuilder:
        match op:
            case BuilderBinaryOp.add:
                lhs = self.expr
                rhs = match_array_concat_arg(
                    (other,),
                    self.wtype.element_type,
                    source_location=location,
                    msg="Array concat expects array or tuple of the same element type. "
                    f"Element type: {self.wtype.element_type}",
                )

                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return var_expression(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=self.wtype,
                    )
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return arc4_bool_bytes(
            expr=self.expr,
            false_bytes=b"\x00\x00",
            location=location,
            negate=negate,
        )


class AppendExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        if not isinstance(expr.wtype, wtypes.ARC4DynamicArray):
            raise InternalError(
                "AppendExpressionBuilder can only be instantiated with an arc4.DynamicArray"
            )
        self.wtype: wtypes.ARC4DynamicArray = expr.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_expr = [expect_arc4_operand_wtype(a, self.wtype.element_type) for a in args]
        args_tuple = TupleExpression.from_items(args_expr, location)
        return var_expression(
            ArrayExtend(
                base=self.expr,
                other=args_tuple,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


class PopExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        if not isinstance(expr.wtype, wtypes.ARC4DynamicArray):
            raise InternalError(
                "AppendExpressionBuilder can only be instantiated with an arc4.DynamicArray"
            )
        self.wtype: wtypes.ARC4DynamicArray = expr.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                return var_expression(
                    ArrayPop(
                        base=self.expr, source_location=location, wtype=self.wtype.element_type
                    )
                )
            case _:
                raise CodeError("Invalid/Unhandled arguments", location)


class ExtendExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, expr: Expression, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        if not isinstance(expr.wtype, wtypes.ARC4DynamicArray):
            raise InternalError(
                "AppendExpressionBuilder can only be instantiated with an arc4.DynamicArray"
            )
        self.wtype: wtypes.ARC4DynamicArray = expr.wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        other = match_array_concat_arg(
            args,
            self.wtype.element_type,
            source_location=location,
            msg="Extend expects an arc4.StaticArray or arc4.DynamicArray of the same element "
            f"type. Expected array or tuple of {self.wtype.element_type}",
        )
        return var_expression(
            ArrayExtend(
                base=self.expr,
                other=other,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


def match_array_concat_arg(
    args: Sequence[ExpressionBuilder | Literal],
    element_type: wtypes.WType,
    *,
    source_location: SourceLocation,
    msg: str,
) -> Expression:
    match args:
        case (ExpressionBuilder() as eb,):
            expr = eb.rvalue()
            match expr:
                case Expression(wtype=wtypes.ARC4Array() as array_wtype) as array_ex:
                    if array_wtype.element_type == element_type:
                        return array_ex
                case Expression(wtype=wtypes.WTuple() as tuple_wtype) as tuple_ex:
                    if all(et == element_type for et in tuple_wtype.types):
                        return tuple_ex
    raise CodeError(msg, source_location)


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

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        if self.wtype.alias != "address":
            return bool_eval_to_constant(
                value=self.wtype.array_size > 0, location=location, negate=negate
            )
        else:
            cmp_with_zero_expr = BytesComparisonExpression(
                lhs=get_bytes_expr(self.expr),
                operator=EqualityComparison.eq if negate else EqualityComparison.ne,
                rhs=intrinsic_factory.zero_address(location, as_type=wtypes.bytes_wtype),
                source_location=location,
            )

            return var_expression(cmp_with_zero_expr)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        if self.wtype.alias != "address":
            return super().compare(other, op=op, location=location)
        match other:
            case Literal(value=str(str_value), source_location=literal_loc):
                rhs = get_bytes_expr(AddressConstant(value=str_value, source_location=literal_loc))
            case ExpressionBuilder(value_type=wtypes.account_wtype):
                rhs = get_bytes_expr(other.rvalue())
            case _:
                return super().compare(other, op=op, location=location)
        cmp_expr = BytesComparisonExpression(
            source_location=location,
            lhs=get_bytes_expr(self.expr),
            operator=EqualityComparison(op.value),
            rhs=rhs,
        )
        return var_expression(cmp_expr)
