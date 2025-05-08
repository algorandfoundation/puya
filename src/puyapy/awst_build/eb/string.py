import typing
from collections.abc import Sequence

from puya import algo_constants, log
from puya.awst import wtypes
from puya.awst.nodes import (
    BoolConstant,
    BytesAugmentedAssignment,
    BytesBinaryOperation,
    BytesBinaryOperator,
    CallArg,
    ConditionalExpression,
    Expression,
    PuyaLibCall,
    PuyaLibFunction,
    Statement,
    StringConstant,
    UInt64Constant,
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
from puyapy.awst_build.eb._utils import compare_bytes, dummy_statement, dummy_value
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class StringTypeBuilder(BytesBackedTypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.StringType, location)

    @typing.override
    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        match literal.value:
            case str(value):
                try:
                    bytes_value = value.encode("utf8")
                except UnicodeEncodeError as ex:
                    logger.error(  # noqa: TRY400
                        f"invalid UTF-8 string (encoding error: {ex})",
                        location=literal.source_location,
                    )
                else:
                    if len(bytes_value) > algo_constants.MAX_BYTES_LENGTH:
                        logger.error(
                            "string constant exceeds max byte array length",
                            location=literal.source_location,
                        )
                expr = StringConstant(value=value, source_location=location)
                return StringExpressionBuilder(expr)
        return None

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.at_most_one_arg(args, location)
        match arg:
            case InstanceBuilder(pytype=pytypes.StrLiteralType):
                return arg.resolve_literal(converter=StringTypeBuilder(location))
            case None:
                str_const = StringConstant(value="", source_location=location)
                return StringExpressionBuilder(str_const)
            case other:
                return expect.not_this_type(
                    other, default=expect.default_dummy_value(self.produces())
                )


class StringExpressionBuilder(BytesBackedInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.StringType, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "startswith":
                return _StringStartsOrEndsWith(self, location, at_start=True)
            case "endswith":
                return _StringStartsOrEndsWith(self, location, at_start=False)
            case "join":
                return _StringJoin(self, location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        if op != BuilderBinaryOp.add:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)
        rhs = expect.argument_of_type_else_dummy(rhs, self.pytype, resolve_literal=True)
        return BytesAugmentedAssignment(
            target=self.resolve_lvalue(),
            op=BytesBinaryOperator.add,
            value=rhs.resolve(),
            source_location=location,
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
        if op != BuilderBinaryOp.add:
            return NotImplemented

        other = other.resolve_literal(converter=StringTypeBuilder(other.source_location))
        # defer to most derived if not equal
        if not (other.pytype <= pytypes.StringType):
            return NotImplemented

        lhs = self.resolve()
        rhs = other.resolve()
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

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        other = other.resolve_literal(converter=StringTypeBuilder(other.source_location))
        return compare_bytes(self=self, op=op, other=other, source_location=location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        len_expr = intrinsic_factory.bytes_len(self.resolve(), location)
        len_builder = UInt64ExpressionBuilder(len_expr)
        return len_builder.bool_eval(location, negate=negate)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        item = expect.argument_of_type_else_dummy(item, pytypes.StringType, resolve_literal=True)
        is_substring_expr = PuyaLibCall(
            func=PuyaLibFunction.is_substring,
            args=[
                CallArg(value=item.resolve(), name=None),
                CallArg(value=self.resolve(), name=None),
            ],
            source_location=location,
        )
        return BoolExpressionBuilder(is_substring_expr)

    @typing.override
    def iterate(self) -> typing.Never:
        raise CodeError(
            "string iteration in not supported due to lack of UTF8 support in AVM",
            self.source_location,
        )

    @typing.override
    def iterable_item_type(self) -> typing.Never:
        self.iterate()

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
    def __init__(self, base: StringExpressionBuilder, location: SourceLocation, *, at_start: bool):
        super().__init__(location)
        self._base = base
        self._at_start = at_start

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args, pytypes.StringType, location, resolve_literal=True
        )
        arg = arg.single_eval()
        this = self._base.single_eval()

        this_length = BytesExpressionBuilder(this.to_bytes(location)).length(location)
        arg_length = BytesExpressionBuilder(arg.to_bytes(location)).length(location)

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
            source_location=location,
        )
        return BoolExpressionBuilder(cond)


class _StringJoin(FunctionBuilder):
    def __init__(self, base: StringExpressionBuilder, location: SourceLocation):
        super().__init__(location)
        self._base = base

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg(args, location, default=expect.default_none)
        if not isinstance(arg, StaticSizedCollectionBuilder):
            if arg is not None:  # if None, already have an error logged
                expect.not_this_type(arg, default=expect.default_none)
            return dummy_value(pytypes.StringType, location)
        items = [
            expect.argument_of_type_else_dummy(
                ib, pytypes.StringType, resolve_literal=True
            ).resolve()
            for ib in arg.iterate_static()
        ]
        sep = self._base.single_eval().resolve()
        joined_value: Expression | None = None
        for item_expr in items:
            if joined_value is None:
                joined_value = item_expr
            else:
                joined_value = intrinsic_factory.concat(
                    intrinsic_factory.concat(joined_value, sep, location),
                    item_expr,
                    location,
                    result_type=wtypes.string_wtype,
                )
        if joined_value is None:
            joined_value = StringConstant(value="", source_location=location)
        return StringExpressionBuilder(joined_value)
