from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoolConstant,
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    BytesComparisonExpression,
    CallArg,
    ConditionalExpression,
    EqualityComparison,
    Expression,
    FreeSubroutineTarget,
    Literal,
    ReinterpretCast,
    SingleEvaluation,
    Statement,
    StringConstant,
    SubroutineCallExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._utils import get_bytes_expr, get_bytes_expr_builder
from puya.awst_build.eb.base import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    ExpressionBuilder,
    FunctionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import convert_literal_to_expr, expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class StringClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.StringType, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case []:
                value = ""
            case [Literal(value=str(value))]:
                pass
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                value = ""
        str_const = StringConstant(value=value, source_location=location)
        return StringExpressionBuilder(str_const)


class StringExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.StringType, expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        match name:
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case "startswith":
                return _StringStartsOrEndsWith(self.expr, location, at_start=True)
            case "endswith":
                return _StringStartsOrEndsWith(self.expr, location, at_start=False)
            case "join":
                return _StringJoin(self.expr, location)
            case _:
                raise CodeError(f"Unrecognised member of {self.wtype}: {name}", location)

    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: ExpressionBuilder | Literal, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return BytesAugmentedAssignment(
                    target=self.lvalue(),
                    op=BytesBinaryOperator.add,
                    value=expect_operand_wtype(rhs, self.wtype),
                    source_location=location,
                )
            case _:
                raise CodeError(
                    f"Unsupported augmented assignment operation on {self.wtype}: {op.value}=",
                    location,
                )

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
                rhs = expect_operand_wtype(other, self.wtype)
                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return StringExpressionBuilder(
                    BytesBinaryOperation(
                        left=lhs,
                        op=BytesBinaryOperator.add,
                        right=rhs,
                        source_location=location,
                    )
                )
            case _:
                return NotImplemented

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        other_expr = convert_literal_to_expr(other, self.wtype)
        if other_expr.wtype == self.wtype:
            pass
        else:
            return NotImplemented
        cmp = BytesComparisonExpression(
            source_location=location,
            lhs=self.expr,
            operator=EqualityComparison(op.value),
            rhs=other_expr,
        )
        return BoolExpressionBuilder(cmp)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        bytes_expr = get_bytes_expr(self.expr)
        len_expr = intrinsic_factory.bytes_len(bytes_expr, location)
        len_builder = UInt64ExpressionBuilder(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> ExpressionBuilder:
        item_expr = get_bytes_expr(expect_operand_wtype(item, wtypes.string_wtype))
        this_expr = get_bytes_expr(self.expr)
        is_substring_expr = SubroutineCallExpression(
            target=FreeSubroutineTarget(module_name="algopy_lib_bytes", name="is_substring"),
            args=[
                CallArg(value=item_expr, name="item"),
                CallArg(value=this_expr, name="sequence"),
            ],
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)


class _StringStartsOrEndsWith(FunctionBuilder):
    def __init__(self, base: Expression, location: SourceLocation, *, at_start: bool):
        super().__init__(location)
        self._base = base
        self._at_start = at_start

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        arg = get_bytes_expr_builder(
            SingleEvaluation(expect_operand_wtype(args[0], wtypes.string_wtype))
        )
        this = get_bytes_expr_builder(SingleEvaluation(self._base))

        this_length = this.member_access("length", location)
        assert isinstance(this_length, ExpressionBuilder)
        arg_length = arg.member_access("length", location)
        assert isinstance(arg_length, ExpressionBuilder)

        arg_length_gt_this_length = arg_length.compare(
            this_length, op=BuilderComparisonOp.gt, location=location
        )

        if self._at_start:
            extracted = intrinsic_factory.extract3(
                this.rvalue(),
                start=UInt64Constant(source_location=location, value=0),
                length=arg_length.rvalue(),
            )
        else:
            extracted = intrinsic_factory.extract3(
                this.rvalue(),
                start=this_length.binary_op(
                    arg_length, BuilderBinaryOp.sub, location, reverse=False
                ).rvalue(),
                length=arg_length.rvalue(),
            )
        this_substr = BytesExpressionBuilder(extracted)

        cond = ConditionalExpression(
            condition=arg_length_gt_this_length.rvalue(),
            true_expr=BoolConstant(location, value=False),
            false_expr=this_substr.compare(arg, BuilderComparisonOp.eq, location).rvalue(),
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(cond)


class _StringJoin(FunctionBuilder):
    def __init__(self, base: Expression, location: SourceLocation):
        super().__init__(location)
        self._base = base

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [
                ExpressionBuilder(value_type=wtypes.WTuple(types=tuple_item_types)) as eb
            ] if all(tt == wtypes.string_wtype for tt in tuple_item_types):
                tuple_arg = SingleEvaluation(eb.rvalue())
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        sep = get_bytes_expr_builder(SingleEvaluation(self._base))
        joined_value: Expression | None = None
        for idx, _ in enumerate(tuple_item_types):
            item_expr = TupleItemExpression(tuple_arg, index=idx, source_location=location)
            bytes_expr = get_bytes_expr(item_expr)
            if joined_value is None:
                joined_value = bytes_expr
            else:
                joined_value = intrinsic_factory.concat(
                    intrinsic_factory.concat(joined_value, sep.rvalue(), location),
                    bytes_expr,
                    location,
                )
        if joined_value is None:
            joined_value = StringConstant(value="", source_location=location)
        return StringExpressionBuilder(
            ReinterpretCast(expr=joined_value, wtype=wtypes.string_wtype, source_location=location)
        )
