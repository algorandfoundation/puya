from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoolConstant,
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    CallArg,
    ConditionalExpression,
    Expression,
    FreeSubroutineTarget,
    SingleEvaluation,
    Statement,
    StringConstant,
    SubroutineCallExpression,
    TupleItemExpression,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
)
from puya.awst_build.eb._bytes_backed import (
    BytesBackedInstanceExpressionBuilder,
    BytesBackedTypeBuilder,
)
from puya.awst_build.eb._utils import compare_bytes
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    LiteralConverter,
    NodeBuilder,
)
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import (
    convert_literal_to_builder,
    expect_operand_type,
    require_instance_builder,
)
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class StringTypeBuilder(BytesBackedTypeBuilder, LiteralConverter):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.StringType, location)

    @typing.override
    @property
    def handled_types(self) -> Collection[pytypes.PyType]:
        return (pytypes.StrLiteralType,)

    @typing.override
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        match literal.value:
            case str(value):
                expr = StringConstant(value=value, source_location=location)
                return StringExpressionBuilder(expr)
        raise CodeError(f"can't covert literal {literal.value!r} to {self.produces()}", location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                value = ""
            case [LiteralBuilder(value=str(value))]:
                pass
            case _:
                logger.error("Invalid/unhandled arguments", location=location)
                # dummy value to continue with
                value = ""
        str_const = StringConstant(value=value, source_location=location)
        return StringExpressionBuilder(str_const)


class StringExpressionBuilder(BytesBackedInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.StringType, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "startswith":
                return _StringStartsOrEndsWith(self.resolve(), location, at_start=True)
            case "endswith":
                return _StringStartsOrEndsWith(self.resolve(), location, at_start=False)
            case "join":
                return _StringJoin(self.resolve(), location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return BytesAugmentedAssignment(
                    target=self.resolve_lvalue(),
                    op=BytesBinaryOperator.add,
                    value=expect_operand_type(rhs, self.pytype).resolve(),
                    source_location=location,
                )
            case _:
                raise CodeError(
                    f"Unsupported augmented assignment operation on {self.pytype}: {op.value}=",
                    location,
                )

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        match op:
            case BuilderBinaryOp.add:
                lhs = self.resolve()
                rhs = expect_operand_type(other, self.pytype).resolve()
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

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = convert_literal_to_builder(other, self.pytype)
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        len_expr = intrinsic_factory.bytes_len(self.resolve(), location)
        len_builder = UInt64ExpressionBuilder(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item = expect_operand_type(item, self.pytype)
        is_substring_expr = SubroutineCallExpression(
            target=FreeSubroutineTarget(module_name="algopy_lib_bytes", name="is_substring"),
            args=[
                CallArg(value=item.to_bytes(item.source_location), name="item"),
                CallArg(value=self.to_bytes(self.source_location), name="sequence"),
            ],
            wtype=wtypes.bool_wtype,
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    @typing.override
    def iterate(self) -> Iteration:
        raise CodeError(
            "string iteration in not supported due to lack of UTF8 support in AVM",
            self.source_location,
        )

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise CodeError(
            "string indexing in not supported due to lack of UTF8 support in AVM", location
        )

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError(
            "string slicing in not supported due to lack of UTF8 support in AVM", location
        )


class _StringStartsOrEndsWith(FunctionBuilder):
    def __init__(self, base: Expression, location: SourceLocation, *, at_start: bool):
        super().__init__(location)
        self._base = base
        self._at_start = at_start

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        arg = StringExpressionBuilder(
            SingleEvaluation(expect_operand_type(args[0], pytypes.StringType).resolve())
        )
        this = StringExpressionBuilder(SingleEvaluation(self._base))

        this_length = require_instance_builder(
            this.member_access("bytes", location).member_access("length", location)
        )
        arg_length = require_instance_builder(
            arg.member_access("bytes", location).member_access("length", location)
        )

        arg_length_gt_this_length = arg_length.compare(
            this_length, op=BuilderComparisonOp.gt, location=location
        )

        if self._at_start:
            extracted = intrinsic_factory.extract3(
                this.resolve(),
                start=UInt64Constant(source_location=location, value=0),
                length=arg_length.resolve(),
                result_type=wtypes.string_wtype,
            )
        else:
            extracted = intrinsic_factory.extract3(
                this.resolve(),
                start=this_length.binary_op(
                    arg_length, BuilderBinaryOp.sub, location, reverse=False
                ).resolve(),
                length=arg_length.resolve(),
                result_type=wtypes.string_wtype,
            )
        this_substr = StringExpressionBuilder(extracted)

        cond = ConditionalExpression(
            condition=arg_length_gt_this_length.resolve(),
            true_expr=BoolConstant(location, value=False),
            false_expr=this_substr.compare(arg, BuilderComparisonOp.eq, location).resolve(),
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
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [InstanceBuilder(pytype=pytypes.TupleType(items=items)) as eb] if all(
                tt == pytypes.StringType for tt in items
            ):
                tuple_arg = SingleEvaluation(eb.resolve())
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        sep = StringExpressionBuilder(SingleEvaluation(self._base))
        joined_value: Expression | None = None
        for idx, _ in enumerate(items):
            item_expr = TupleItemExpression(tuple_arg, index=idx, source_location=location)
            if joined_value is None:
                joined_value = item_expr
            else:
                joined_value = intrinsic_factory.concat(
                    intrinsic_factory.concat(joined_value, sep.resolve(), location),
                    item_expr,
                    location,
                    result_type=wtypes.string_wtype,
                )
        if joined_value is None:
            joined_value = StringConstant(value="", source_location=location)
        return StringExpressionBuilder(joined_value)
