import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import (
    BinaryBooleanOperator,
    Enumeration,
    Expression,
    IntegerConstant,
    Lvalue,
    Range,
    Reversed,
    Statement,
    UInt64Constant,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import GenericTypeBuilder
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    BuilderUnaryOp,
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class UnsignedRangeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.urangeType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        assert set(arg_names) == {None}
        uint64_args = [
            expect.argument_of_type_else_dummy(in_arg, pytypes.UInt64Type, resolve_literal=True)
            for in_arg in args
        ]
        first, rest = expect.at_least_one_arg(
            uint64_args, location, default=expect.default_dummy_value(pytypes.UInt64Type)
        )
        match rest:
            case []:
                range_stop = first
                range_start: InstanceBuilder = UInt64ExpressionBuilder(
                    UInt64Constant(value=0, source_location=location)
                )
                range_step: InstanceBuilder = UInt64ExpressionBuilder(
                    UInt64Constant(value=1, source_location=location)
                )
            case [range_stop]:
                range_start = first
                range_step = UInt64ExpressionBuilder(
                    UInt64Constant(value=1, source_location=location)
                )
            case [range_stop, range_step, *extra]:
                range_start = first
                if isinstance(range_step, IntegerConstant) and range_step.value == 0:
                    logger.error(
                        "urange step size cannot be zero", location=range_step.source_location
                    )
                if extra:
                    logger.error(
                        f"expected at most 3 arguments, got {len(args)}", location=location
                    )
            case _:
                raise InternalError("UH OH SPAGHETTI-O's !!! 🤠🍝🌵️", location)

        return _RangeIterBuilder(
            source_location=location,
            start=range_start,
            stop=range_stop,
            step=range_step,
        )


class UnsignedEnumerateBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        # note: we actually expect exactly 1, but want to provide special error message
        #       in case of extra params
        sequence, extra = expect.at_least_one_arg(args, location, default=expect.default_raise)
        if extra:
            logger.error(
                "unlike enumerate(), uenumerate() does not support a start parameter "
                "(ie, start must always be zero)",
                location=location,
            )
        return _EnumerateIterBuilder(sequence, location)


class ReversedFunctionExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        sequence = expect.exactly_one_arg(args, location, default=expect.default_raise)
        return _ReversedIterBuilder(sequence, location)


class _IterableOnlyBuilder(InstanceBuilder, abc.ABC):
    @typing.override
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return self.try_resolve_literal(converter)

    @typing.override
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        return self

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self._iterable_only(location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def resolve(self) -> Expression:
        return self._iterable_only(self.source_location)

    @typing.override
    def resolve_lvalue(self) -> Lvalue:
        return self._iterable_only(self.source_location)

    @typing.override
    def delete(self, location: SourceLocation) -> Statement:
        return self._iterable_only(location)

    @typing.override
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        return self._iterable_only(location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        return self._iterable_only(location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        return self._iterable_only(location)

    def _iterable_only(self, location: SourceLocation) -> typing.Never:
        raise CodeError("expression is only usable as the source of a for-loop", location)


class _RangeIterBuilder(_IterableOnlyBuilder):
    def __init__(
        self,
        start: InstanceBuilder,
        stop: InstanceBuilder,
        step: InstanceBuilder,
        source_location: SourceLocation,
    ):
        super().__init__(source_location)
        self._start = start
        self._stop = stop
        self._step = step

    @typing.override
    @property
    def pytype(self) -> pytypes.PyType:
        return pytypes.urangeType

    @typing.override
    def iterate(self) -> Expression:
        return Range(
            start=self._start.resolve(),
            stop=self._stop.resolve(),
            step=self._step.resolve(),
            source_location=self.source_location,
        )

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return pytypes.UInt64Type

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        return _RangeIterBuilder(
            start=self._start.single_eval(),
            stop=self._stop.single_eval(),
            step=self._step.single_eval(),
            source_location=self.source_location,
        )


class _EnumerateIterBuilder(_IterableOnlyBuilder):
    def __init__(self, sequence: InstanceBuilder, source_location: SourceLocation):
        super().__init__(source_location)
        self._sequence = sequence

    @typing.override
    @property
    def pytype(self) -> pytypes.PyType:
        # TODO: this should be parametrised using the sequence item pytype
        return pytypes.uenumerateGenericType

    @typing.override
    def iterate(self) -> Expression:
        return Enumeration(expr=self._sequence.iterate(), source_location=self.source_location)

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        item_type = self._sequence.iterable_item_type()
        return pytypes.GenericTupleType.parameterise(
            [pytypes.UInt64Type, item_type], self.source_location
        )

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        return _EnumerateIterBuilder(self._sequence.single_eval(), self.source_location)


class _ReversedIterBuilder(_IterableOnlyBuilder):
    def __init__(self, sequence: InstanceBuilder, source_location: SourceLocation):
        super().__init__(source_location)
        self._sequence = sequence

    @typing.override
    @property
    def pytype(self) -> pytypes.PyType:
        # TODO: this should be parametrised using the sequence item pytype
        return pytypes.reversedGenericType

    @typing.override
    def iterate(self) -> Expression:
        return Reversed(expr=self._sequence.iterate(), source_location=self.source_location)

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self._sequence.iterable_item_type()

    @typing.override
    def single_eval(self) -> InstanceBuilder:
        return _ReversedIterBuilder(self._sequence.single_eval(), self.source_location)
