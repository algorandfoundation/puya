import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    ArrayConcat,
    ArrayLength,
    ArrayReplace,
    AssignmentStatement,
    Expression,
    IndexExpression,
    IntersectionSliceExpression,
    NewArray,
    Statement,
    TupleExpression,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceExpressionBuilder,
)
from puyapy.awst_build.eb._utils import (
    dummy_statement,
    dummy_value,
    resolve_negative_literal_index,
)
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    BuilderBinaryOp,
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.awst_build.eb.uint64 import UInt64ExpressionBuilder

logger = log.get_logger(__name__)


class ImmutableArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        element_type = expect.instance_builder(args[0], default=expect.default_raise).pytype
        typ = pytypes.GenericImmutableArrayType.parameterise([element_type], location)
        return ImmutableArrayTypeBuilder(typ, self.source_location).call(
            args, arg_kinds, arg_names, location
        )


class ImmutableArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericImmutableArrayType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.StackArray)
        self._wtype = wtype
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        values = tuple(expect.argument_of_type_else_dummy(a, typ.items).resolve() for a in args)
        return ImmutableArrayExpressionBuilder(
            NewArray(values=values, wtype=self._wtype, source_location=location), self._pytype
        )


class ImmutableArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(typ, expr)

    @typing.override
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        logger.error("item containment with arrays is currently unsupported", location=location)
        return dummy_value(pytypes.BoolType, location)

    @typing.override
    def iterate(self) -> Expression:
        return self.resolve()

    @typing.override
    def iterable_item_type(self) -> pytypes.PyType:
        return self.pytype.items

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        array_length = self.length(index.source_location)
        index = resolve_negative_literal_index(index, array_length, location)
        result_expr = IndexExpression(
            base=self.resolve(),
            index=index.resolve(),
            source_location=location,
        )
        return builder_for_instance(self.pytype.items, result_expr)

    @typing.override
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing arrays is currently unsupported", location)

    @typing.override
    @typing.final
    def to_bytes(self, location: SourceLocation) -> Expression:
        return self.resolve()

    def length(self, location: SourceLocation) -> InstanceBuilder:
        return UInt64ExpressionBuilder(ArrayLength(array=self.resolve(), source_location=location))

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return self.length(location)
            case "replace":
                return _Replace(self.resolve(), self.pytype, location)
            case "append":
                return _Append(self.resolve(), self.pytype, location)
            case "pop":
                return _Pop(self.resolve(), self.pytype, location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        # only __add__ is implemented, not __radd__
        if op != BuilderBinaryOp.add or reverse:
            return NotImplemented

        other = _match_array_concat_arg(other, self.pytype)
        return ImmutableArrayExpressionBuilder(
            ArrayConcat(
                left=self.resolve(),
                right=other.resolve(),
                source_location=location,
            ),
            self.pytype,
        )

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        if op != BuilderBinaryOp.add:
            logger.error(f"unsupported operator for type: {op.value!r}", location=location)
            return dummy_statement(location)
        lhs = self.single_eval().resolve_lvalue()
        rhs = _match_array_concat_arg(rhs, self.pytype)
        return AssignmentStatement(
            target=lhs,
            value=ArrayConcat(
                left=lhs,
                right=rhs.resolve(),
                source_location=location,
            ),
            source_location=location,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return self.length(location).bool_eval(location, negate=negate)


class _ArrayFunc(FunctionBuilder, abc.ABC):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ


class _Append(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(args, self.typ.items, location)
        args_expr = arg.resolve()
        args_tuple = TupleExpression.from_items([args_expr], arg.source_location)
        return ImmutableArrayExpressionBuilder(
            ArrayConcat(
                left=self.expr,
                right=args_tuple,
                source_location=location,
            ),
            self.typ,
        )


class _Pop(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        return ImmutableArrayExpressionBuilder(
            IntersectionSliceExpression(
                base=self.expr,
                begin_index=None,
                end_index=-1,
                wtype=self.typ.wtype,
                source_location=location,
            ),
            self.typ,
        )


class _Replace(_ArrayFunc):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if expect.exactly_n_args(args, location, 2):
            index = expect.argument_of_type_else_dummy(
                args[0], pytypes.UInt64Type, resolve_literal=True
            )
            value = expect.argument_of_type_else_dummy(args[1], self.typ.items)
        else:
            index = dummy_value(pytypes.UInt64Type, location)
            value = dummy_value(self.typ.items, location)
        return ImmutableArrayExpressionBuilder(
            ArrayReplace(
                base=self.expr,
                index=index.resolve(),
                value=value.resolve(),
                source_location=location,
            ),
            self.typ,
        )


def _check_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> bool:
    match arg:
        case InstanceBuilder(pytype=pytypes.ArrayType(items=arr_type.items)):
            return True
        case InstanceBuilder(pytype=pytypes.TupleLikeType(items=tup_items)) if all(
            ti == arr_type.items for ti in tup_items
        ):
            return True
    return False


def _match_array_concat_arg(arg: InstanceBuilder, arr_type: pytypes.ArrayType) -> InstanceBuilder:
    if _check_array_concat_arg(arg, arr_type):
        return arg
    logger.error(
        "expected an array or tuple of the same element type", location=arg.source_location
    )
    return dummy_value(arr_type, arg.source_location)
