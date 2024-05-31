from __future__ import annotations

import typing
from abc import ABC

from puya import log
from puya.algo_constants import ENCODED_ADDRESS_LENGTH
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    ArrayConcat,
    ArrayExtend,
    ArrayPop,
    CheckedMaybe,
    Expression,
    ExpressionStatement,
    IndexExpression,
    IntrinsicCall,
    NewArray,
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
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import (
    FunctionBuilder,
    GenericTypeBuilder,
    InstanceExpressionBuilder,
)
from puya.awst_build.eb._utils import (
    bool_eval_to_constant,
    compare_bytes,
    compare_expr_bytes,
    get_bytes_expr_builder,
)
from puya.awst_build.eb.arc4._utils import expect_arc4_operand_pytype
from puya.awst_build.eb.arc4.base import CopyBuilder, arc4_bool_bytes
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import (
    BuilderBinaryOp,
    BuilderComparisonOp,
    InstanceBuilder,
    Iteration,
    LiteralBuilder,
    NodeBuilder,
)
from puya.awst_build.eb.reference_types.account import AccountExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import (
    expect_operand_type,
    require_instance_builder,
)
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class DynamicArrayGenericClassExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("Empty arrays require a type annotation to be instantiated", location)
        non_literal_args = [require_instance_builder(a) for a in args]
        element_type = arg_typs[0]

        for a in non_literal_args:
            expect_operand_type(a, element_type)

        typ = pytypes.GenericARC4DynamicArrayType.parameterise([element_type], location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        return DynamicArrayExpressionBuilder(
            NewArray(
                values=tuple(a.rvalue() for a in non_literal_args),
                wtype=wtype,
                source_location=location,
            ),
            typ,
        )


class DynamicArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4DynamicArrayType
        assert typ.size is None
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        non_literal_args = [require_instance_builder(a) for a in args]
        typ = self.produces()
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4DynamicArray)
        for a in non_literal_args:
            expect_operand_type(a, typ.items)

        return DynamicArrayExpressionBuilder(
            NewArray(
                values=tuple(a.rvalue() for a in non_literal_args),
                wtype=wtype,
                source_location=location,
            ),
            self._pytype,
        )


class StaticArrayGenericClassExpressionBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("Empty arrays require a type annotation to be instantiated", location)
        non_literal_args = [require_instance_builder(a) for a in args]
        element_type = arg_typs[0]
        array_size = len(non_literal_args)
        typ = pytypes.GenericARC4StaticArrayType.parameterise(
            [element_type, pytypes.TypingLiteralType(value=array_size, source_location=None)],
            location,
        )

        for a in non_literal_args:
            expect_operand_type(a, element_type)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(
                source_location=location,
                values=tuple(a.rvalue() for a in non_literal_args),
                wtype=wtype,
            ),
            typ,
        )


class StaticArrayClassExpressionBuilder(BytesBackedClassExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4StaticArrayType
        assert typ.size is not None
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        non_literal_args = [require_instance_builder(a) for a in args]
        typ = self.produces()
        if typ.size != len(non_literal_args):
            raise CodeError(f"{typ} should be initialized with {typ.size} values", location)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)

        for a in non_literal_args:
            expect_operand_type(a, typ.items)

        return StaticArrayExpressionBuilder(
            NewArray(
                values=tuple(a.rvalue() for a in non_literal_args),
                wtype=wtype,
                source_location=location,
            ),
            self.produces(),
        )


class AddressClassExpressionBuilder(BytesBackedClassExpressionBuilder[pytypes.ArrayType]):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.ARC4AddressType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        wtype = self.produces().wtype
        match args:
            case []:
                result: Expression = intrinsic_factory.zero_address(location, as_type=wtype)
            case [LiteralBuilder(value=str(addr_value))]:
                if not wtypes.valid_address(addr_value):
                    raise CodeError(
                        f"Invalid address value. Address literals should be"
                        f" {ENCODED_ADDRESS_LENGTH} characters and not include base32 padding",
                        location,
                    )
                result = AddressConstant(
                    value=addr_value,
                    wtype=wtype,
                    source_location=location,
                )
            case [InstanceBuilder(pytype=pytypes.AccountType) as eb]:
                result = _address_from_native(eb)
            case [InstanceBuilder(pytype=pytypes.BytesType) as eb]:
                value = eb.rvalue()
                address_bytes_temp = SingleEvaluation(value)
                is_correct_length = NumericComparisonExpression(
                    operator=NumericComparison.eq,
                    source_location=location,
                    lhs=UInt64Constant(value=32, source_location=location),
                    rhs=intrinsic_factory.bytes_len(address_bytes_temp, location),
                )
                result = CheckedMaybe.from_tuple_items(
                    expr=ReinterpretCast(
                        expr=address_bytes_temp,
                        wtype=wtype,
                        source_location=address_bytes_temp.source_location,
                    ),
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
        return AddressExpressionBuilder(result)


class _ARC4ArrayExpressionBuilder(InstanceExpressionBuilder[pytypes.ArrayType], ABC):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType):
        self.pytyp = typ
        super().__init__(typ, expr)

    @typing.override
    def iterate(self) -> Iteration:
        if not self.pytype.items.wtype.immutable:
            logger.error(
                "Cannot directly iterate an ARC4 array of mutable objects,"
                " construct a for-loop over the indexes via urange(<array>.length) instead",
                location=self.source_location,
            )
        return self.rvalue()

    @typing.override
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        if isinstance(index, LiteralBuilder) and isinstance(index.value, int) and index.value < 0:
            index_expr: Expression = UInt64BinaryOperation(
                left=expect_operand_type(
                    self.member_access("length", index.source_location), pytypes.UInt64Type
                ).rvalue(),
                op=UInt64BinaryOperator.sub,
                right=UInt64Constant(
                    value=abs(index.value), source_location=index.source_location
                ),
                source_location=index.source_location,
            )
        else:
            index_expr = expect_operand_type(index, pytypes.UInt64Type).rvalue()
        result_expr = IndexExpression(
            base=self.expr,
            index=index_expr,
            wtype=self.pytype.items.wtype,
            source_location=location,
        )
        return builder_for_instance(self.pytyp.items, result_expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case "copy":
                return CopyBuilder(self.expr, location, self.pytyp)
            case _:
                return super().member_access(name, location)

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        return compare_bytes(lhs=self, op=op, rhs=other, source_location=location)

    @typing.override
    @typing.final
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        raise CodeError("item containment with ARC4 arrays is currently unsupported", location)

    @typing.override
    @typing.final
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("slicing ARC4 arrays is currently unsupported", location)


class DynamicArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        super().__init__(expr, typ)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    IntrinsicCall(
                        op_code="extract_uint16",
                        stack_args=[self.expr, UInt64Constant(value=0, source_location=location)],
                        source_location=location,
                        wtype=wtypes.uint64_wtype,
                    )
                )
            case "append":
                return _Append(self.expr, self.pytyp, location)
            case "extend":
                return _Extend(self.expr, self.pytyp, location)
            case "pop":
                return _Pop(self.expr, self.pytyp, location)
            case _:
                return super().member_access(name, location)

    @typing.override
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        match op:
            case BuilderBinaryOp.add:
                return ExpressionStatement(
                    expr=ArrayExtend(
                        base=self.expr,
                        other=match_array_concat_arg(
                            (rhs,),
                            self.pytype.items.wtype,
                            source_location=location,
                            msg="Array concat expects array or tuple of the same element type. "
                            f"Element type: {self.pytype.items}",
                        ),
                        source_location=location,
                        wtype=wtypes.arc4_string_wtype,
                    )
                )
            case _:
                return super().augmented_assignment(op, rhs, location)

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
                lhs = self.expr
                rhs = match_array_concat_arg(
                    (other,),
                    self.pytype.items.wtype,
                    source_location=location,
                    msg="Array concat expects array or tuple of the same element type. "
                    f"Element type: {self.pytype.items}",
                )

                if reverse:
                    (lhs, rhs) = (rhs, lhs)
                return DynamicArrayExpressionBuilder(
                    ArrayConcat(
                        left=lhs,
                        right=rhs,
                        source_location=location,
                        wtype=self.pytyp.wtype,
                    ),
                    self.pytyp,
                )

            case _:
                return super().binary_op(other, op, location, reverse=reverse)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return arc4_bool_bytes(
            self,
            false_bytes=b"\x00\x00",
            location=location,
            negate=negate,
        )


class _Append(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:

        args_expr = [expect_arc4_operand_pytype(a, self.typ.items) for a in args]
        args_tuple = TupleExpression.from_items(args_expr, location)
        return VoidExpressionBuilder(
            ArrayExtend(
                base=self.expr,
                other=args_tuple,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


class _Pop(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case []:
                result_expr = ArrayPop(
                    base=self.expr, source_location=location, wtype=self.typ.items.wtype
                )
                return builder_for_instance(self.typ.items, result_expr)
            case _:
                raise CodeError("Invalid/Unhandled arguments", location)


class _Extend(FunctionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.ArrayType, location: SourceLocation):
        super().__init__(location)
        self.expr = expr
        self.typ = typ

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        other = match_array_concat_arg(
            args,
            self.typ.items.wtype,
            source_location=location,
            msg="Extend expects an arc4.StaticArray or arc4.DynamicArray of the same element "
            f"type. Expected array or tuple of {self.typ.items}",
        )
        return VoidExpressionBuilder(
            ArrayExtend(
                base=self.expr,
                other=other,
                source_location=location,
                wtype=wtypes.void_wtype,
            )
        )


def match_array_concat_arg(
    args: Sequence[NodeBuilder],
    element_type: wtypes.WType,
    *,
    source_location: SourceLocation,
    msg: str,
) -> Expression:
    match args:
        case (InstanceBuilder() as eb,):
            expr = eb.rvalue()
            match expr:
                case Expression(wtype=wtypes.ARC4Array() as array_wtype) as array_ex:
                    if array_wtype.element_type == element_type:
                        return array_ex
                case Expression(wtype=wtypes.WTuple() as tuple_wtype) as tuple_ex:
                    if all(et == element_type for et in tuple_wtype.types):
                        return tuple_ex
    raise CodeError(msg, source_location)


class StaticArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        size = typ.size
        assert size is not None
        self._size = size
        super().__init__(expr, typ)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    UInt64Constant(value=self._size, source_location=location)
                )
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=self._size > 0, location=location, negate=negate)


class AddressExpressionBuilder(StaticArrayExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(expr, pytypes.ARC4AddressType)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return compare_expr_bytes(
            lhs=self.rvalue(),
            op=BuilderComparisonOp.eq if negate else BuilderComparisonOp.ne,
            rhs=intrinsic_factory.zero_address(location, as_type=self.pytype.wtype),
            source_location=location,
        )

    @typing.override
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        match other:
            case LiteralBuilder(value=str(str_value), source_location=literal_loc):
                rhs: Expression = AddressConstant(
                    value=str_value, wtype=self.pytype.wtype, source_location=literal_loc
                )
            case InstanceBuilder(pytype=pytypes.AccountType):
                rhs = _address_from_native(other)
            case InstanceBuilder(pytype=pytypes.ARC4AddressType):
                rhs = other.rvalue()
            case _:
                return NotImplemented
        return compare_expr_bytes(lhs=self.rvalue(), op=op, rhs=rhs, source_location=location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "native":
                return AccountExpressionBuilder(_address_to_native(self))
            case _:
                return super().member_access(name, location)


def _address_to_native(builder: InstanceBuilder) -> Expression:
    assert builder.pytype == pytypes.ARC4AddressType
    return ReinterpretCast(
        expr=builder.rvalue(), wtype=wtypes.account_wtype, source_location=builder.source_location
    )


def _address_from_native(builder: InstanceBuilder) -> Expression:
    assert builder.pytype == pytypes.AccountType
    return ReinterpretCast(
        expr=builder.rvalue(),
        wtype=wtypes.arc4_address_type,
        source_location=builder.source_location,
    )
