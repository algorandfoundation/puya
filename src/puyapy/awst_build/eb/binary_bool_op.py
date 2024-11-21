import typing

from puya.awst.nodes import (
    BinaryBooleanOperator,
    BooleanBinaryOperation,
    ConditionalExpression,
    Expression,
    Not,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.bool import BoolExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.utils import determine_base_type


class BinaryBoolOpBuilder(InstanceBuilder):
    """
    This builder works to defer the evaluation of a boolean binary op (ie and/or), because
    in some cases (unions, python literals) we can only successfully evaluate in certain contexts.

    For example:
        a = Bytes(...)
        b = UInt64(...)
        if a or b: # this is fine, even though `a or b` produces `Bytes | UInt64`
            ...
        c = a or b # compiler error

    You wouldn't be able to do anything with c, since in general we can't know at compile
    time what the type of c is, and the AVM doesn't provide any type introspection.
    Even if there was an op that said whether a stack item or a scratch slot etc held
    a bytes[] or a uint64, there are differences between logical types and physical types
    that need to be accounted for - for example, biguint is a bytes[] but we would need
    to use a different equality op b== instead of ==
    """

    def __init__(
        self,
        left: InstanceBuilder,
        right: InstanceBuilder,
        op: BinaryBooleanOperator,
        location: SourceLocation,
        *,
        result_type: pytypes.PyType | None = None,
    ):
        super().__init__(location)
        if result_type is None:
            # if either left or right is already a union, just produce another union
            if isinstance(left.pytype, pytypes.UnionType) or isinstance(
                right.pytype, pytypes.UnionType
            ):
                # note if left and/or right are unions this constructor will expand them for us
                result_type = pytypes.UnionType([left.pytype, right.pytype], location)
            else:
                # otherwise, left and right are both non-union types, so try and
                # compute a common base type, falling back to a union if not possible
                result_type = determine_base_type(left.pytype, right.pytype, location=location)
        self._result_type = result_type
        self._left = left
        self._right = right
        self._op = op

    @typing.override
    @property
    def pytype(self) -> pytypes.PyType:
        return self._result_type

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        left = self._left.single_eval()
        right = self._right.single_eval()
        return self._evolve_builders(left, right, recalculate_type=False)

    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        left = self._left.resolve_literal(converter)
        right = self._right.resolve_literal(converter)
        return self._evolve_builders(left, right)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder | None:
        left = self._left.try_resolve_literal(converter)
        right = self._right.try_resolve_literal(converter)
        if left is None or right is None:
            return None
        return self._evolve_builders(left, right)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        bool_left = self._left.bool_eval(self._left.source_location).resolve()
        bool_right = self._right.bool_eval(self._right.source_location).resolve()
        result_expr: Expression = BooleanBinaryOperation(
            left=bool_left, op=self._op, right=bool_right, source_location=location
        )
        if negate:
            result_expr = Not(expr=result_expr, source_location=location)
        return BoolExpressionBuilder(result_expr)

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return BinaryBoolOpBuilder(left=self, right=other, op=op, location=location)

    @typing.override
    def resolve(self) -> Expression:
        if isinstance(self.pytype, pytypes.UnionType):
            raise CodeError(
                "expression would produce a union type,"
                " which isn't supported unless evaluating a boolean condition",
                self.source_location,
            )
        result_wtype = self.pytype.checked_wtype(self.source_location)

        # (left:uint64 and right:uint64) => left_cache if not bool(left_cache := left) else right
        # (left:uint64 or right:uint64) => left_cache if bool(left_cache := left) else right
        left_cache = self._left.single_eval()
        condition = left_cache.bool_eval(
            self.source_location, negate=self._op is BinaryBooleanOperator.and_
        )
        expr_result = ConditionalExpression(
            condition=condition.resolve(),
            true_expr=left_cache.resolve(),
            false_expr=self._right.resolve(),
            wtype=result_wtype,
            source_location=self.source_location,
        )
        return expr_result

    def _evolve_builders(
        self, left: InstanceBuilder, right: InstanceBuilder, *, recalculate_type: bool = True
    ) -> InstanceBuilder:
        return BinaryBoolOpBuilder(
            left=left,
            right=right,
            op=self._op,
            location=self.source_location,
            result_type=None if recalculate_type else self.pytype,
        )

    # region Invalid Python syntax
    @typing.override
    def resolve_lvalue(self) -> typing.Never:
        raise CodeError(
            # message copied from Python
            "cannot assign to expression here. Maybe you meant '==' instead of '='?",
            self.source_location,
        )

    @typing.override
    def delete(self, location: SourceLocation) -> typing.Never:
        raise CodeError(
            # message copied from Python
            "cannot delete expression",
            location,
        )

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, right: InstanceBuilder, location: SourceLocation
    ) -> typing.Never:
        raise CodeError(
            # copied (and trimmed) from Python
            "illegal expression for augmented assignment",
            location,
        )

    # endregion

    # region Forward to resolved builder
    def _resolve_builder(self) -> InstanceBuilder:
        expr = self.resolve()
        return builder_for_instance(self.pytype, expr)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        return self._resolve_builder().unary_op(op, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return self._resolve_builder().compare(other, op, location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return self._resolve_builder().binary_op(other, op, location, reverse=reverse)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._resolve_builder().contains(item, location)

    @typing.override
    def iterate(self) -> Expression:
        return self._resolve_builder().iterate()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self._resolve_builder().iterable_item_type()

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._resolve_builder().index(index, location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return self._resolve_builder().slice_index(begin_index, end_index, stride, location)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self._resolve_builder().to_bytes(location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        return self._resolve_builder().member_access(name, location)

    # endregion
