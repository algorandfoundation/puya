import decimal
import enum
import itertools
import typing
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya.avm_type import AVMType
from puya.awst import wtypes
from puya.awst.txn_fields import TxnField
from puya.awst.visitors import ExpressionVisitor, ModuleStatementVisitor, StatementVisitor
from puya.awst.wtypes import WType
from puya.errors import CodeError, InternalError
from puya.models import (
    ARC4MethodConfig,
    ContractReference,
    LogicSigReference,
)
from puya.parse import SourceLocation
from puya.utils import StableSet

T = typing.TypeVar("T")

ConstantValue: typing.TypeAlias = int | str | bytes | bool


@attrs.frozen
class Node:
    source_location: SourceLocation


@attrs.frozen
class Statement(Node, ABC):
    @abstractmethod
    def accept(self, visitor: StatementVisitor[T]) -> T: ...


@attrs.frozen
class Expression(Node, ABC):
    wtype: WType

    @abstractmethod
    def accept(self, visitor: ExpressionVisitor[T]) -> T: ...


@attrs.frozen(init=False)
class ExpressionStatement(Statement):
    expr: Expression

    def __init__(self, expr: Expression):
        self.__attrs_init__(expr=expr, source_location=expr.source_location)

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_expression_statement(self)


@attrs.frozen(repr=False)
class _ExpressionHasWType:
    instances: tuple[WType, ...]
    types: tuple[type[WType], ...]

    def __call__(
        self,
        inst: Node,
        attr: attrs.Attribute,  # type: ignore[type-arg]
        value: Expression,
    ) -> None:
        """
        We use a callable class to be able to change the ``__repr__``.
        """
        wtype = value.wtype
        if wtype in self.instances:
            return
        for allowed_t in self.types:
            if isinstance(wtype, allowed_t):
                return
        raise InternalError(
            f"{type(inst).__name__}.{attr.name}: expression of WType {wtype} received,"
            f" expected {' or '.join(self._names)}"
        )

    def __repr__(self) -> str:
        return f"<expression_has_wtype validator for type {' | '.join(self._names)}>"

    @property
    def _names(self) -> Iterator[str]:
        for inst in self.instances:
            yield inst.name
        for typ in self.types:
            yield typ.__name__


def expression_has_wtype(*one_of_these: WType | type[WType]) -> _ExpressionHasWType:
    instances = []
    types = list[type[WType]]()
    for item in one_of_these:
        if isinstance(item, type):
            types.append(item)
        else:
            instances.append(item)
    return _ExpressionHasWType(instances=tuple(instances), types=tuple(types))


@attrs.frozen(repr=False)
class _WTypeIsOneOf:
    instances: tuple[WType, ...]
    types: tuple[type[WType], ...]

    def __call__(
        self,
        inst: Node,
        attr: attrs.Attribute,  # type: ignore[type-arg]
        value: WType,
    ) -> None:
        """
        We use a callable class to be able to change the ``__repr__``.
        """
        wtype = value
        if wtype in self.instances:
            return
        for allowed_t in self.types:
            if isinstance(wtype, allowed_t):
                return
        raise InternalError(
            f"{type(inst).__name__}.{attr.name}: set to {wtype},"
            f" expected {' or '.join(self._names)}"
        )

    def __repr__(self) -> str:
        return f"<expression_has_wtype validator for type {' | '.join(self._names)}>"

    @property
    def _names(self) -> Iterator[str]:
        for inst in self.instances:
            yield inst.name
        for typ in self.types:
            yield typ.__name__


def wtype_is_one_of(*one_of_these: WType | type[WType]) -> _WTypeIsOneOf:
    instances = []
    types = list[type[WType]]()
    for item in one_of_these:
        if isinstance(item, type):
            types.append(item)
        else:
            instances.append(item)
    return _WTypeIsOneOf(instances=tuple(instances), types=tuple(types))


wtype_is_uint64 = expression_has_wtype(wtypes.uint64_wtype)
wtype_is_biguint = expression_has_wtype(wtypes.biguint_wtype)
wtype_is_bool = expression_has_wtype(wtypes.bool_wtype)
wtype_is_bytes = expression_has_wtype(wtypes.bytes_wtype)

Label = typing.NewType("Label", str)


@attrs.frozen(kw_only=True)
class Block(Statement):
    """
    A (non-basic) block used to group statements. Can contain nested blocks, loops, and branching
    structures. No lexical scoping is offered or implied by this block.

    body: A sequence of statements which represent this block
    comment: An optional comment of what this block represents. Only influences
                 non-functional output
    label: An optional label for this block allowing goto statements to jump to this block.
           Must be unique per subroutine.
    """

    body: Sequence[Statement] = attrs.field(converter=tuple[Statement, ...])
    label: Label | None = None
    comment: str | None = None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_block(self)


@attrs.frozen(kw_only=True)
class Goto(Statement):
    """
    Branch unconditionally to the block with the specified label.

    target: The label of a block within the same subroutine
    """

    target: Label

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_goto(self)


@attrs.frozen
class IfElse(Statement):
    condition: Expression = attrs.field(validator=[wtype_is_bool])
    if_branch: Block
    else_branch: Block | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_if_else(self)


@attrs.frozen
class Switch(Statement):
    value: Expression
    cases: Mapping[Expression, Block] = attrs.field(converter=immutabledict)
    default_case: Block | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_switch(self)


@attrs.frozen
class WhileLoop(Statement):
    condition: Expression = attrs.field(validator=[wtype_is_bool])
    loop_body: Block

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_while_loop(self)


@attrs.frozen
class LoopExit(Statement):
    """break out of the current innermost loop"""

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_loop_exit(self)


@attrs.frozen
class LoopContinue(Statement):
    """continue with the next iteration of the current innermost loop"""

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_loop_continue(self)


@attrs.frozen
class ReturnStatement(Statement):
    value: Expression | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_return_statement(self)


@attrs.frozen(kw_only=True)
class IntegerConstant(Expression):
    wtype: WType = attrs.field(
        validator=[
            wtype_is_one_of(
                wtypes.uint64_wtype,
                wtypes.biguint_wtype,
                wtypes.ARC4UIntN,
            )
        ]
    )
    value: int = attrs.field()
    teal_alias: str | None = None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_integer_constant(self)


@attrs.frozen
class DecimalConstant(Expression):
    wtype: wtypes.ARC4UFixedNxM
    value: decimal.Decimal = attrs.field()

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_decimal_constant(self)


def UInt64Constant(  # noqa: N802
    *, source_location: SourceLocation, value: int, teal_alias: str | None = None
) -> IntegerConstant:
    return IntegerConstant(
        source_location=source_location,
        value=value,
        wtype=wtypes.uint64_wtype,
        teal_alias=teal_alias,
    )


def BigUIntConstant(  # noqa: N802
    *, source_location: SourceLocation, value: int
) -> IntegerConstant:
    return IntegerConstant(
        source_location=source_location,
        value=value,
        wtype=wtypes.biguint_wtype,
    )


@attrs.frozen
class BoolConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)
    value: bool

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bool_constant(self)


@enum.unique
class BytesEncoding(enum.StrEnum):
    unknown = enum.auto()
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    utf8 = enum.auto()


@attrs.frozen(repr=False)
class _WTypeIsBackedBy:
    backed_by: typing.Literal[AVMType.uint64, AVMType.bytes]

    def __call__(
        self,
        inst: Node,
        attr: attrs.Attribute,  # type: ignore[type-arg]
        value: WType,
    ) -> None:
        """
        We use a callable class to be able to change the ``__repr__``.
        """
        if not isinstance(inst, Node):
            raise InternalError(f"{self!r} used on type {type(inst).__name__}, expected Node")
        if value.scalar_type != self.backed_by:
            raise InternalError(
                f"{type(inst).__name__}.{attr.name}: set to {value},"
                f" which is not backed by {value.scalar_type}, not {self.backed_by.name}"
            )

    def __repr__(self) -> str:
        return f"<wtype_is_{self.backed_by.name}_backed validator>"


wtype_is_bytes_backed: typing.Final = _WTypeIsBackedBy(backed_by=AVMType.bytes)
wtype_is_uint64_backed: typing.Final = _WTypeIsBackedBy(backed_by=AVMType.uint64)


@attrs.frozen(kw_only=True)
class BytesConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, validator=wtype_is_bytes_backed)
    value: bytes = attrs.field()
    encoding: BytesEncoding = attrs.field()

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_constant(self)


@attrs.frozen
class StringConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.string_wtype, init=False)
    value: str = attrs.field()

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_string_constant(self)


@attrs.frozen
class TemplateVar(Expression):
    wtype: WType
    name: str

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_template_var(self)


@attrs.frozen
class MethodConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, init=False)
    value: str

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_method_constant(self)


@attrs.frozen(kw_only=True)
class AddressConstant(Expression):
    wtype: WType = attrs.field(
        default=wtypes.account_wtype,
        validator=wtype_is_one_of(wtypes.account_wtype, wtypes.arc4_address_alias),
    )
    value: str

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_address_constant(self)


@attrs.frozen
class ARC4Encode(Expression):
    value: Expression
    wtype: wtypes.ARC4Type = attrs.field()

    @wtype.validator
    def _wtype_validator(self, _attribute: object, wtype: wtypes.ARC4Type) -> None:
        if self.value.wtype not in wtype.encodeable_types:
            raise InternalError(
                f"cannot ARC4 encode {self.value.wtype} to {wtype}", self.source_location
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_arc4_encode(self)


@attrs.frozen
class Copy(Expression):
    """
    Create a new copy of 'value'
    """

    value: Expression
    wtype: WType = attrs.field(init=False)

    @wtype.default
    def _wtype(self) -> WType:
        return self.value.wtype

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_copy(self)


@attrs.frozen
class ArrayConcat(Expression):
    """
    Given 'left' or 'right' that is logically an array - concat it with the other value which is
    an iterable type with the same element type
    """

    left: Expression
    right: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_array_concat(self)


@attrs.frozen
class ArrayPop(Expression):
    base: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_array_pop(self)


@attrs.frozen
class ArrayExtend(Expression):
    """
    Given 'base' that is logically an array - extend it with 'other' which is an iterable type with
    the same element type
    """

    base: Expression
    other: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_array_extend(self)


@attrs.frozen
class ARC4Decode(Expression):
    value: Expression = attrs.field()

    @value.validator
    def _value_wtype_validator(self, _attribute: object, value: Expression) -> None:
        if not isinstance(value.wtype, wtypes.ARC4Type):
            raise InternalError(
                f"ARC4Decode should only be used with expressions of ARC4Type, got {value.wtype}",
                self.source_location,
            )
        if self.wtype != value.wtype.decode_type:
            raise InternalError(
                f"ARC4Decode from {value.wtype} should have target type {value.wtype.decode_type},"
                f" got {self.wtype}",
                self.source_location,
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_arc4_decode(self)


CompileTimeConstantExpression: typing.TypeAlias = (
    IntegerConstant
    | DecimalConstant
    | BoolConstant
    | BytesConstant
    | AddressConstant
    | MethodConstant
)


@attrs.define
class IntrinsicCall(Expression):
    op_code: str
    immediates: Sequence[str | int] = attrs.field(default=(), converter=tuple[str | int, ...])
    stack_args: Sequence[Expression] = attrs.field(default=(), converter=tuple[Expression, ...])
    comment: str | None = attrs.field(default=None)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_intrinsic_call(self)


@attrs.define
class CreateInnerTransaction(Expression):
    wtype: wtypes.WInnerTransactionFields
    fields: Mapping[TxnField, Expression] = attrs.field(converter=immutabledict)

    @fields.validator
    def _validate_fields(self, _attribute: object, fields: Mapping[TxnField, Expression]) -> None:
        for field, value in fields.items():
            if not field.valid_argument_type(value.wtype):
                raise CodeError("invalid type for field", value.source_location)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_create_inner_transaction(self)


@attrs.define
class UpdateInnerTransaction(Expression):
    itxn: Expression = attrs.field(validator=expression_has_wtype(wtypes.WInnerTransactionFields))
    fields: Mapping[TxnField, Expression] = attrs.field(converter=immutabledict)
    wtype: WType = attrs.field(default=wtypes.void_wtype, init=False)

    @fields.validator
    def _validate_fields(self, _attribute: object, fields: Mapping[TxnField, Expression]) -> None:
        for field, value in fields.items():
            if not field.valid_argument_type(value.wtype):
                raise CodeError("invalid type for field", value.source_location)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_update_inner_transaction(self)


@attrs.define(init=False)
class CheckedMaybe(Expression):
    """Allows evaluating a maybe type i.e. tuple[_T, bool] as _T, but with the assertion that
    the 2nd bool element is true"""

    expr: Expression
    comment: str

    def __init__(self, expr: Expression, comment: str) -> None:
        match expr.wtype:
            case wtypes.WTuple(types=(wtype, wtypes.bool_wtype)):
                pass
            case _:
                raise InternalError(
                    f"{type(self).__name__}.expr: expression of WType {expr.wtype} received,"
                    f" expected tuple[_T, bool]"
                )
        self.__attrs_init__(
            source_location=expr.source_location,
            expr=expr,
            comment=comment,
            wtype=wtype,
        )

    @classmethod
    def from_tuple_items(
        cls,
        expr: Expression,
        check: Expression,
        source_location: SourceLocation,
        comment: str,
    ) -> typing.Self:
        if check.wtype != wtypes.bool_wtype:
            raise InternalError(
                "Check condition for CheckedMaybe should be a boolean", source_location
            )
        tuple_expr = TupleExpression.from_items((expr, check), source_location)
        return cls(expr=tuple_expr, comment=comment)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_checked_maybe(self)


@attrs.frozen
class TupleExpression(Expression):
    items: Sequence[Expression] = attrs.field(converter=tuple[Expression, ...])
    wtype: wtypes.WTuple = attrs.field()

    @classmethod
    def from_items(cls, items: Sequence[Expression], location: SourceLocation) -> typing.Self:
        return cls(
            items=items,
            wtype=wtypes.WTuple((i.wtype for i in items), location),
            source_location=location,
        )

    @wtype.validator
    def _wtype_validator(self, _attribute: object, wtype: wtypes.WTuple) -> None:
        if tuple(it.wtype for it in self.items) != wtype.types:
            raise CodeError("Tuple type mismatch", self.source_location)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_tuple_expression(self)


@attrs.frozen(init=False)
class TupleItemExpression(Expression):
    """Represents tuple element access.

    Note: this is its own item (vs IndexExpression) for two reasons:
    1. It's not a valid lvalue (tuples are immutable)
    2. The index must always be a literal, and can be negative
    """

    base: Expression
    index: int

    def __init__(self, base: Expression, index: int, source_location: SourceLocation) -> None:
        base_wtype = base.wtype
        if not isinstance(base_wtype, wtypes.WTuple | wtypes.ARC4Tuple):
            raise InternalError(
                f"Tuple item expression should be for a tuple type, got {base_wtype}",
                source_location,
            )
        try:
            wtype = base_wtype.types[index]
        except IndexError as ex:
            raise CodeError("invalid index into tuple expression", source_location) from ex
        self.__attrs_init__(
            source_location=source_location,
            base=base,
            index=index,
            wtype=wtype,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_tuple_item_expression(self)


@attrs.frozen
class VarExpression(Expression):
    name: str

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_var_expression(self)


@attrs.frozen(kw_only=True)
class InnerTransactionField(Expression):
    itxn: Expression = attrs.field(validator=expression_has_wtype(wtypes.WInnerTransaction))
    field: TxnField
    array_index: Expression | None = None

    def __attrs_post_init__(self) -> None:
        has_array = self.array_index is not None
        if has_array != self.field.is_array:
            raise InternalError(
                f"Inconsistent field and array_index combination: "
                f"{self.field} and {'' if has_array else 'no '} array provided",
                self.source_location,
            )
        if self.wtype.scalar_type != self.field.avm_type:
            raise InternalError(
                f"wtype of field {self.field.immediate} is {self.field.wtype}"
                f" which is not compatible with specified result type {self.wtype}",
                self.source_location,
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_inner_transaction_field(self)


@attrs.define
class SubmitInnerTransaction(Expression):
    group: Expression | tuple[Expression, ...] = attrs.field()
    wtype: WType = attrs.field(init=False)

    @wtype.default
    def _wtype(self) -> wtypes.WType:
        if isinstance(self.group, tuple):
            txn_types = []
            for expr in self.group:
                if not isinstance(expr.wtype, wtypes.WInnerTransactionFields):
                    raise CodeError("invalid expression type for submit", expr.source_location)
                txn_types.append(wtypes.WInnerTransaction.from_type(expr.wtype.transaction_type))
            return wtypes.WTuple(txn_types, self.source_location)
        if not isinstance(self.group.wtype, wtypes.WInnerTransactionFields):
            raise CodeError("invalid expression type for submit", self.group.source_location)
        return wtypes.WInnerTransaction.from_type(self.group.wtype.transaction_type)

    @property
    def itxns(self) -> tuple[Expression, ...]:
        if isinstance(self.group, tuple):
            return self.group
        return (self.group,)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_submit_inner_transaction(self)


@attrs.frozen
class FieldExpression(Expression):
    base: Expression = attrs.field(
        validator=expression_has_wtype(wtypes.WStructType, wtypes.ARC4Struct)
    )
    name: str
    wtype: wtypes.WType = attrs.field(init=False)

    @wtype.default
    def _wtype_factory(self) -> wtypes.WType:
        struct_wtype = self.base.wtype
        if not isinstance(struct_wtype, wtypes.WStructType | wtypes.ARC4Struct):
            raise InternalError("invalid struct wtype")
        try:
            return struct_wtype.fields[self.name]
        except KeyError:
            raise CodeError(f"invalid field for {struct_wtype}", self.source_location) from None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_field_expression(self)


@attrs.frozen
class IndexExpression(Expression):
    base: Expression = attrs.field(
        validator=expression_has_wtype(
            wtypes.bytes_wtype,
            wtypes.ARC4StaticArray,
            wtypes.ARC4DynamicArray,
            # NOTE: tuples (native or arc4) use TupleItemExpression instead
        )
    )
    index: Expression = attrs.field(validator=expression_has_wtype(wtypes.uint64_wtype))

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_index_expression(self)


@attrs.frozen
class SliceExpression(Expression):

    base: Expression = attrs.field(
        validator=expression_has_wtype(
            wtypes.bytes_wtype,
            wtypes.WTuple,
        )
    )

    begin_index: Expression | None
    end_index: Expression | None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_slice_expression(self)


@attrs.frozen
class IntersectionSliceExpression(Expression):
    """
    Returns the intersection of the slice indexes and the base
    """

    base: Expression = attrs.field(
        validator=expression_has_wtype(
            wtypes.bytes_wtype,
            wtypes.WTuple,
        )
    )

    begin_index: Expression | int | None
    end_index: Expression | int | None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_intersection_slice_expression(self)


@attrs.frozen
class AppStateExpression(Expression):
    key: Expression = attrs.field(validator=expression_has_wtype(wtypes.state_key))
    exists_assertion_message: str | None
    """TEAL comment that will be emitted in a checked-read scenario"""

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_app_state_expression(self)


@attrs.frozen
class AppAccountStateExpression(Expression):
    key: Expression = attrs.field(validator=expression_has_wtype(wtypes.state_key))
    exists_assertion_message: str | None
    """TEAL comment that will be emitted in a checked-read scenario"""
    account: Expression = attrs.field(
        validator=expression_has_wtype(wtypes.account_wtype, wtypes.uint64_wtype)
    )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_app_account_state_expression(self)


@attrs.frozen
class BoxValueExpression(Expression):
    key: Expression = attrs.field(validator=expression_has_wtype(wtypes.box_key))
    exists_assertion_message: str | None
    """TEAL comment that will be emitted in a checked-read scenario"""

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_box_value_expression(self)


@attrs.frozen
class SingleEvaluation(Expression):
    """
    This node wraps an underlying expression and effectively caches the result of that lowering,
    such that regardless of how many times the SingleEvaluation object
    (or any object comparing equal to it) appears in the AWST,
    the underlying source expression will only be evaluated once.
    """

    source: Expression
    _id: int = attrs.field()
    wtype: WType = attrs.field(init=False, eq=False)
    source_location: SourceLocation = attrs.field(eq=False)

    @_id.default
    def _default_id(self) -> int:
        return id(self)

    @wtype.default
    def _wtype(self) -> WType:
        return self.source.wtype

    @source_location.default
    def _default_source_location(self) -> SourceLocation:
        return self.source.source_location

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_single_evaluation(self)


@attrs.frozen
class ReinterpretCast(Expression):
    """Convert an expression to an AVM equivalent type.

    Note: the validation of this isn't done until IR construction"""

    expr: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_reinterpret_cast(self)


StorageExpression = AppStateExpression | AppAccountStateExpression | BoxValueExpression
# Expression types that are valid on the left hand side of assignment *statements*
# Note that some of these can be recursive/nested, eg:
# obj.field[index].another_field = 123
Lvalue = VarExpression | FieldExpression | IndexExpression | TupleExpression | StorageExpression


@attrs.frozen
class NewArray(Expression):
    wtype: wtypes.WArray | wtypes.ARC4Array
    values: Sequence[Expression] = attrs.field(default=(), converter=tuple[Expression, ...])

    @values.validator
    def _check_element_types(self, _attribute: object, value: tuple[Expression, ...]) -> None:
        if any(expr.wtype != self.wtype.element_type for expr in value):
            raise ValueError(
                f"All array elements should have array type: {self.wtype.element_type}"
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_new_array(self)


@attrs.frozen
class ConditionalExpression(Expression):
    """A "ternary" operator with conditional evaluation - the true and false expressions must only
    be evaluated if they will be the result of expression.
    """

    condition: Expression = attrs.field(validator=[wtype_is_bool])
    true_expr: Expression
    false_expr: Expression
    wtype: WType = attrs.field()

    @wtype.default
    def _wtype(self) -> WType:
        if self.true_expr.wtype != self.false_expr.wtype:
            raise CodeError(
                f"true and false expressions of conditional have differing types:"
                f" {self.true_expr.wtype} and {self.false_expr.wtype}",
                self.source_location,
            )
        return self.true_expr.wtype

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_conditional_expression(self)


@attrs.frozen
class AssignmentStatement(Statement):
    """
    A single assignment statement e.g. `a = 1`.

    Multi-assignment statements like `a = b = 1` should be split in the AST pass.

    Will validate that target and value are of the same type, and that said type is usable
    as an l-value.
    """

    target: Lvalue
    value: Expression

    def __attrs_post_init__(self) -> None:
        if self.value.wtype != self.target.wtype:
            raise CodeError(
                "assignment target type differs from expression value type",
                self.source_location,
            )
        if self.value.wtype == wtypes.void_wtype:
            raise CodeError("void type cannot be assigned", self.source_location)

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assignment_statement(self)


@attrs.frozen(init=False)
class AssignmentExpression(Expression):
    """
    This both assigns value to target and returns the target as the result of the expression.

    Note that tuple expressions aren't valid here as the target, but tuple variables obviously are.

    Will validate that target and value are of the same type, and that said type is usable
    as an l-value.
    """

    target: Lvalue  # annoyingly, we can't do Lvalue "minus" TupleExpression
    value: Expression

    def __init__(self, value: Expression, target: Lvalue, source_location: SourceLocation):
        if isinstance(target, TupleExpression):
            raise CodeError(
                "tuple unpacking in assignment expressions is not supported",
                target.source_location,
            )
        if value.wtype != target.wtype:
            raise CodeError(
                "assignment target type differs from expression value type",
                source_location,
            )
        if value.wtype == wtypes.void_wtype:
            raise CodeError("void type cannot be assigned", source_location)
        self.__attrs_init__(
            source_location=source_location,
            target=target,
            value=value,
            wtype=target.wtype,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_assignment_expression(self)


class EqualityComparison(enum.StrEnum):
    eq = "=="
    ne = "!="


class NumericComparison(enum.StrEnum):
    eq = "=="  # 😩 why can't Python have enum inheritance
    ne = "!="
    lt = "<"
    lte = "<="
    gt = ">"
    gte = ">="


numeric_comparable = expression_has_wtype(
    wtypes.uint64_wtype,
    wtypes.biguint_wtype,
    wtypes.bool_wtype,
    wtypes.asset_wtype,
    wtypes.application_wtype,
)


@attrs.frozen
class NumericComparisonExpression(Expression):
    """Compare two numeric types.

    Any type promotion etc should be done at the source language level,
    this operation expects both arguments to already be in the same type.
    This is to insulate against language-specific differences in type promotion rules,
    or equality comparisons with bool, and so on.
    """

    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    # TODO: make these names consistent with other expressions
    lhs: Expression = attrs.field(validator=[numeric_comparable])
    operator: NumericComparison
    rhs: Expression = attrs.field(validator=[numeric_comparable])

    def __attrs_post_init__(self) -> None:
        if self.lhs.wtype != self.rhs.wtype:
            raise InternalError(
                "numeric comparison between different wtypes:"
                f" {self.lhs.wtype} and {self.rhs.wtype}",
                self.source_location,
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_numeric_comparison_expression(self)


bytes_comparable = expression_has_wtype(
    wtypes.bytes_wtype,
    wtypes.account_wtype,
    wtypes.string_wtype,
    wtypes.ARC4Type,
)


@attrs.frozen
class BytesComparisonExpression(Expression):
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    lhs: Expression = attrs.field(validator=[bytes_comparable])
    operator: EqualityComparison
    rhs: Expression = attrs.field(validator=[bytes_comparable])

    def __attrs_post_init__(self) -> None:
        if self.lhs.wtype != self.rhs.wtype:
            raise InternalError(
                "bytes comparison between different wtypes:"
                f" {self.lhs.wtype} and {self.rhs.wtype}",
                self.source_location,
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_comparison_expression(self)


@attrs.frozen
class InstanceSubroutineTarget:
    name: str


@attrs.frozen
class BaseClassSubroutineTarget:
    base_class: ContractReference
    name: str


@attrs.frozen
class FreeSubroutineTarget:
    module_name: str  # module name the subroutine resides in
    name: str  # name of the subroutine within the module


@attrs.frozen
class CallArg:
    name: str | None  # if None, then passed positionally
    value: Expression


SubroutineTarget = FreeSubroutineTarget | InstanceSubroutineTarget | BaseClassSubroutineTarget


@attrs.frozen
class SubroutineCallExpression(Expression):
    target: SubroutineTarget
    args: Sequence[CallArg] = attrs.field(converter=tuple[CallArg, ...])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_subroutine_call_expression(self)


@enum.unique
class UInt64BinaryOperator(enum.StrEnum):
    add = "+"
    sub = "-"
    mult = "*"
    floor_div = "//"
    mod = "%"
    pow = "**"
    lshift = "<<"
    rshift = ">>"
    bit_or = "|"
    bit_xor = "^"
    bit_and = "&"
    # unsupported:
    # / aka ast.Div
    # @ aka ast.MatMult


@enum.unique
class BigUIntBinaryOperator(enum.StrEnum):
    add = "+"
    sub = "-"
    mult = "*"
    floor_div = "//"
    mod = "%"
    bit_or = "|"
    bit_xor = "^"
    bit_and = "&"
    # unsupported:
    # ** aka ast.Pow
    # / aka ast.Div
    # @ aka ast.MatMult
    # << aka ast.LShift
    # >> aka ast.RShift


@enum.unique
class BytesBinaryOperator(enum.StrEnum):
    add = "+"
    bit_or = "|"
    bit_xor = "^"
    bit_and = "&"


@enum.unique
class BytesUnaryOperator(enum.StrEnum):
    bit_invert = "~"


@enum.unique
class UInt64UnaryOperator(enum.StrEnum):
    bit_invert = "~"


@enum.unique
class UInt64PostfixUnaryOperator(enum.StrEnum):
    increment = "++"
    decrement = "--"


@attrs.frozen
class UInt64UnaryOperation(Expression):
    op: UInt64UnaryOperator
    expr: Expression = attrs.field(validator=[wtype_is_uint64])
    wtype: WType = attrs.field(default=wtypes.uint64_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_uint64_unary_operation(self)


@attrs.frozen
class UInt64PostfixUnaryOperation(Expression):
    op: UInt64PostfixUnaryOperator
    target: Lvalue = attrs.field(validator=[wtype_is_uint64])
    wtype: WType = attrs.field(default=wtypes.uint64_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_uint64_postfix_unary_operation(self)


@enum.unique
class BigUIntPostfixUnaryOperator(enum.StrEnum):
    increment = "++"
    decrement = "--"


@attrs.frozen
class BigUIntPostfixUnaryOperation(Expression):
    op: BigUIntPostfixUnaryOperator
    target: Expression = attrs.field(validator=[wtype_is_biguint])
    wtype: WType = attrs.field(default=wtypes.biguint_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_biguint_postfix_unary_operation(self)


@attrs.frozen
class BytesUnaryOperation(Expression):
    op: BytesUnaryOperator
    expr: Expression = attrs.field(validator=[wtype_is_bytes])
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_unary_operation(self)


@attrs.frozen
class UInt64BinaryOperation(Expression):
    left: Expression = attrs.field(validator=[wtype_is_uint64])
    op: UInt64BinaryOperator
    right: Expression = attrs.field(validator=[wtype_is_uint64])
    wtype: WType = attrs.field(default=wtypes.uint64_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_uint64_binary_operation(self)


@attrs.frozen
class BigUIntBinaryOperation(Expression):
    left: Expression = attrs.field(validator=[wtype_is_biguint])
    op: BigUIntBinaryOperator
    right: Expression = attrs.field(validator=[wtype_is_biguint])
    wtype: WType = attrs.field(default=wtypes.biguint_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_biguint_binary_operation(self)


@attrs.frozen
class BytesBinaryOperation(Expression):
    left: Expression = attrs.field(
        validator=[expression_has_wtype(wtypes.bytes_wtype, wtypes.string_wtype)]
    )
    op: BytesBinaryOperator
    right: Expression = attrs.field(
        validator=[expression_has_wtype(wtypes.bytes_wtype, wtypes.string_wtype)]
    )
    wtype: WType = attrs.field(init=False)

    @right.validator
    def _check_right(self, _attribute: object, right: Expression) -> None:
        if right.wtype != self.left.wtype:
            raise CodeError(
                f"Bytes operation on differing types,"
                f" lhs is {self.left.wtype}, rhs is {self.right.wtype}",
                self.source_location,
            )

    @wtype.default
    def _wtype_factory(self) -> wtypes.WType:
        return self.left.wtype

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_binary_operation(self)


@enum.unique
class BinaryBooleanOperator(enum.StrEnum):
    and_ = "and"
    or_ = "or"


@attrs.frozen
class BooleanBinaryOperation(Expression):
    left: Expression = attrs.field(validator=[wtype_is_bool])
    op: BinaryBooleanOperator
    right: Expression = attrs.field(validator=[wtype_is_bool])
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_boolean_binary_operation(self)


@attrs.frozen
class Not(Expression):
    expr: Expression = attrs.field(validator=[wtype_is_bool])
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_not_expression(self)


@attrs.frozen
class UInt64AugmentedAssignment(Statement):
    target: Lvalue = attrs.field(validator=[wtype_is_uint64])
    op: UInt64BinaryOperator
    value: Expression = attrs.field(validator=[wtype_is_uint64])

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_uint64_augmented_assignment(self)


@attrs.frozen
class BigUIntAugmentedAssignment(Statement):
    target: Lvalue = attrs.field(validator=[wtype_is_biguint])
    op: BigUIntBinaryOperator
    value: Expression = attrs.field(validator=[wtype_is_biguint])

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_biguint_augmented_assignment(self)


@attrs.frozen
class BytesAugmentedAssignment(Statement):
    target: Lvalue = attrs.field(
        validator=[expression_has_wtype(wtypes.bytes_wtype, wtypes.string_wtype)]
    )
    op: BytesBinaryOperator
    value: Expression = attrs.field(
        validator=[expression_has_wtype(wtypes.bytes_wtype, wtypes.string_wtype)]
    )

    @value.validator
    def _check_value(self, _attribute: object, value: Expression) -> None:
        if value.wtype != self.target.wtype:
            raise CodeError(
                f"Augmented assignment of differing types,"
                f" expected {self.target.wtype}, got {value.wtype}",
                value.source_location,
            )

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_bytes_augmented_assignment(self)


@attrs.frozen
class Range(Node):
    start: Expression = attrs.field(validator=[wtype_is_uint64])
    stop: Expression = attrs.field(validator=[wtype_is_uint64])
    step: Expression = attrs.field(validator=[wtype_is_uint64])


@attrs.frozen
class OpUp(Node):
    n: Expression


@attrs.frozen(init=False)
class Enumeration(Expression):
    expr: Expression | Range

    def __init__(self, expr: Expression | Range, source_location: SourceLocation):
        item_wtype = expr.wtype if isinstance(expr, Expression) else wtypes.uint64_wtype
        wtype = wtypes.WTuple((wtypes.uint64_wtype, item_wtype), source_location)
        self.__attrs_init__(
            expr=expr,
            source_location=source_location,
            wtype=wtype,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_enumeration(self)


@attrs.frozen(init=False)
class Reversed(Expression):
    expr: Expression | Range

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_reversed(self)

    def __init__(self, expr: Expression | Range, source_location: SourceLocation):
        wtype = expr.wtype if isinstance(expr, Expression) else wtypes.uint64_wtype

        self.__attrs_init__(
            expr=expr,
            source_location=source_location,
            wtype=wtype,
        )


@attrs.frozen
class ForInLoop(Statement):
    sequence: Expression | Range
    items: Lvalue  # item variable(s)
    loop_body: Block

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_for_in_loop(self)


@attrs.frozen
class StateGet(Expression):
    """
    Get value or default if unset - note that for get without a default,
    can just use the underlying StateExpression
    """

    field: StorageExpression
    default: Expression = attrs.field()
    wtype: WType = attrs.field(init=False)

    @default.validator
    def _check_default(self, _attribute: object, default: Expression) -> None:
        if self.field.wtype != default.wtype:
            raise CodeError(
                "Default state value should match storage type", default.source_location
            )

    @wtype.default
    def _wtype_factory(self) -> WType:
        return self.field.wtype

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_state_get(self)


@attrs.frozen
class StateGetEx(Expression):
    field: StorageExpression
    wtype: wtypes.WTuple = attrs.field(init=False)

    @wtype.default
    def _wtype_factory(self) -> wtypes.WTuple:
        return wtypes.WTuple(
            (self.field.wtype, wtypes.bool_wtype),
            self.source_location,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_state_get_ex(self)


@attrs.frozen
class StateExists(Expression):
    field: StorageExpression
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_state_exists(self)


@attrs.frozen
class StateDelete(Expression):
    field: StorageExpression
    wtype: WType = attrs.field(default=wtypes.void_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_state_delete(self)


@attrs.frozen
class NewStruct(Expression):
    wtype: wtypes.WStructType | wtypes.ARC4Struct
    values: Mapping[str, Expression] = attrs.field(converter=immutabledict)

    @values.validator
    def _validate_values(self, _instance: object, values: Mapping[str, Expression]) -> None:
        if values.keys() != self.wtype.fields.keys():
            raise CodeError("Invalid argument(s)", self.source_location)
        for field_name, field_value in self.values.items():
            expected_wtype = self.wtype.fields[field_name]
            if field_value.wtype != expected_wtype:
                raise CodeError("Invalid argument type(s)", self.source_location)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_new_struct(self)


@attrs.frozen
class ModuleStatement(Node, ABC):
    name: str

    @abstractmethod
    def accept(self, visitor: ModuleStatementVisitor[T]) -> T: ...


@attrs.frozen
class ConstantDeclaration(ModuleStatement):
    value: ConstantValue

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_constant_declaration(self)


@attrs.frozen
class SubroutineArgument(Node):
    name: str
    wtype: WType = attrs.field()

    @wtype.validator
    def _wtype_validator(self, _attribute: object, wtype: WType) -> None:
        if wtype == wtypes.void_wtype:
            raise CodeError("void type arguments are not supported", self.source_location)


@attrs.frozen
class Function(ModuleStatement, ABC):
    module_name: str
    args: Sequence[SubroutineArgument] = attrs.field(converter=tuple[SubroutineArgument, ...])
    return_type: WType
    body: Block
    docstring: str | None

    @property
    @abstractmethod
    def full_name(self) -> str: ...


@attrs.frozen
class Subroutine(Function):
    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.name))

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_subroutine(self)


@attrs.frozen
class ContractMethod(Function):
    class_name: str
    arc4_method_config: ARC4MethodConfig | None

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.class_name, self.name))

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_contract_method(self)


@enum.unique
class AppStorageKind(enum.Enum):
    app_global = enum.auto()
    account_local = enum.auto()
    box = enum.auto()


@attrs.frozen
class AppStorageDefinition(Node):
    member_name: str
    kind: AppStorageKind
    storage_wtype: WType
    key_wtype: WType | None
    """if not None, then this is a map rather than singular"""
    key: BytesConstant
    """for maps, this is the prefix"""
    description: str | None


@attrs.frozen
class LogicSignature(ModuleStatement):
    module_name: str
    program: Subroutine = attrs.field()

    @program.validator
    def _validate_program(self, _instance: object, program: Subroutine) -> None:
        if program.args:
            raise CodeError(
                "logicsig should not take any args",
                program.args[0].source_location,
            )
        if program.return_type not in (wtypes.uint64_wtype, wtypes.bool_wtype):
            raise CodeError(
                "Invalid return type for logicsig method, should be either bool or UInt64.",
                program.source_location,
            )

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.name))

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_logic_signature(self)


@attrs.frozen
class CompiledContract(Expression):
    contract: ContractReference
    allocation_overrides: Mapping[TxnField, Expression] = attrs.field(
        factory=immutabledict, converter=immutabledict
    )
    prefix: str | None = None
    """
    Prefix will either be the value specified here or PuyaOptions.template_vars_prefix
    if prefix is None

    The prefix is then prefixed with the template_variables keys on this node to determine the
    final template variable name
    """
    template_variables: Mapping[str, Expression] = attrs.field(
        factory=immutabledict, converter=immutabledict
    )
    """
    template variables combined with their prefix defined on this node take precedence over
    template variables of the same key defined on PuyaOptions
    """

    @allocation_overrides.validator
    def _allocation_overrides(
        self, _attribute: object, value: Mapping[TxnField, Expression]
    ) -> None:
        if value.keys() - {
            TxnField.ExtraProgramPages,
            TxnField.GlobalNumUint,
            TxnField.GlobalNumByteSlice,
            TxnField.LocalNumUint,
            TxnField.LocalNumByteSlice,
        }:
            raise InternalError("only allocation fields can be overridden", self.source_location)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_compiled_contract(self)


@attrs.frozen
class CompiledLogicSig(Expression):
    logic_sig: LogicSigReference
    prefix: str | None = None
    template_variables: Mapping[str, Expression] = attrs.field(
        converter=immutabledict, factory=immutabledict
    )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_compiled_logicsig(self)


@attrs.frozen(kw_only=True)
class StateTotals:
    global_uints: int | None = None
    local_uints: int | None = None
    global_bytes: int | None = None
    local_bytes: int | None = None


@attrs.frozen
class ContractFragment(ModuleStatement):
    # note: it's a fragment because it needs to be stitched together with bases,
    #       assuming it's not abstract (in which case it should remain a fragment?)
    module_name: str
    name_override: str | None
    is_abstract: bool
    is_arc4: bool
    bases: Sequence[ContractReference] = attrs.field(converter=tuple[ContractReference, ...])
    init: ContractMethod | None = attrs.field()
    approval_program: ContractMethod | None = attrs.field()
    clear_program: ContractMethod | None = attrs.field()
    subroutines: Sequence[ContractMethod] = attrs.field(converter=tuple[ContractMethod, ...])
    app_state: Mapping[str, AppStorageDefinition]
    reserved_scratch_space: StableSet[int]
    state_totals: StateTotals | None
    docstring: str | None
    # note: important that this comes last so default factory has access to all other fields
    methods: Mapping[str, ContractMethod] = attrs.field(init=False)

    @methods.default
    def _methods_factory(self) -> Mapping[str, ContractMethod]:
        result: dict[str, ContractMethod] = {}
        all_subs = itertools.chain(
            filter(None, (self.init, self.approval_program, self.clear_program)),
            self.subroutines,
        )
        for sub in all_subs:
            if sub.name in result or sub.name in self.app_state:
                raise CodeError(
                    f"Duplicate symbol {sub.name} in contract {self.full_name}",
                    sub.source_location,
                )
            result[sub.name] = sub
        return result

    @init.validator
    def check_init(self, _attribute: object, init: ContractMethod | None) -> None:
        if init is not None:
            if init.return_type != wtypes.void_wtype:
                raise CodeError("init methods cannot return a value", init.source_location)
            if init.args:
                raise CodeError(
                    "init method should take no arguments (other than self)",
                    init.source_location,
                )
            if init.arc4_method_config is not None:
                raise CodeError(
                    "init method should not be marked as an ABI method", init.source_location
                )

    @approval_program.validator
    def check_approval(self, _attribute: object, approval: ContractMethod | None) -> None:
        if approval is not None:
            if approval.args:
                raise CodeError(
                    "approval method should not take any args (other than self)",
                    approval.source_location,
                )
            if approval.return_type not in (wtypes.uint64_wtype, wtypes.bool_wtype):
                raise CodeError(
                    "Invalid return type for approval method, should be either bool or UInt64.",
                    approval.source_location,
                )
            if approval.arc4_method_config:
                raise CodeError(
                    "approval method should not be marked as an ABI method",
                    approval.source_location,
                )

    @clear_program.validator
    def check_clear(self, _attribute: object, clear: ContractMethod | None) -> None:
        if clear is not None:
            if clear.args:
                raise CodeError(
                    "clear-state method should not take any args (other than self)",
                    clear.source_location,
                )
            if clear.return_type not in (wtypes.uint64_wtype, wtypes.bool_wtype):
                raise CodeError(
                    "Invalid return type for clear-state method, should be either bool or UInt64.",
                    clear.source_location,
                )
            if clear.arc4_method_config:
                raise CodeError(
                    "clear-state method should not be marked as an ABI method",
                    clear.source_location,
                )

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.name))

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_contract_fragment(self)


@attrs.frozen
class StructureField(Node):
    name: str
    wtype: WType


@attrs.frozen
class StructureDefinition(ModuleStatement):
    fields: Sequence[StructureField] = attrs.field(converter=tuple[StructureField, ...])
    wtype: WType
    docstring: str | None

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_structure_definition(self)


@attrs.frozen
class Module:
    name: str
    source_file_path: str
    body: Sequence[ModuleStatement] = attrs.field(converter=tuple[ModuleStatement, ...])

    @cached_property
    def symtable(self) -> Mapping[str, ModuleStatement]:
        return {stmt.name: stmt for stmt in self.body}
