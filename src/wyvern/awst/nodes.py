import enum
import typing as t
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from functools import cached_property

import attrs

from wyvern.awst import wtypes
from wyvern.awst.visitors import (
    ExpressionVisitor,
    ModuleStatementVisitor,
    StatementVisitor,
)
from wyvern.awst.wtypes import WType
from wyvern.errors import CodeError, InternalError
from wyvern.parse import SourceLocation

T = t.TypeVar("T")

ConstantValue: t.TypeAlias = int | str | bytes | bool


@attrs.frozen
class Node:
    source_location: SourceLocation


@attrs.frozen
class Statement(Node, ABC):
    @abstractmethod
    def accept(self, visitor: StatementVisitor[T]) -> T:
        ...


@attrs.frozen
class Expression(Node, ABC):
    wtype: WType

    @abstractmethod
    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        ...


@attrs.frozen(init=False)
class ExpressionStatement(Statement):
    expr: Expression

    def __init__(self, expr: Expression):
        self.__attrs_init__(expr=expr, source_location=expr.source_location)

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_expression_statement(self)


@attrs.frozen(repr=False)
class _ExpressionHasWType:
    one_of_these: tuple[WType, ...]

    def __call__(
        self,
        inst: Node,
        attr: attrs.Attribute,  # type: ignore[type-arg]
        value: Expression,
    ) -> None:
        """
        We use a callable class to be able to change the ``__repr__``.
        """
        if value.wtype not in self.one_of_these:
            raise InternalError(
                f"{type(inst).__name__}.{attr.name}: expression of WType {value.wtype} received,"
                f" expected {' or '.join(map(str, self.one_of_these))}"
            )

    def __repr__(self) -> str:
        return (
            f"<expression_has_wtype validator"
            f" for type {' | '.join(map(str, self.one_of_these))}>"
        )


def expression_has_wtype(*one_of_these: WType) -> _ExpressionHasWType:
    return _ExpressionHasWType(one_of_these)


wtype_is_uint64 = expression_has_wtype(wtypes.uint64_wtype)
wtype_is_biguint = expression_has_wtype(wtypes.biguint_wtype)
wtype_is_bool = expression_has_wtype(wtypes.bool_wtype)
wtype_is_bytes = expression_has_wtype(wtypes.bytes_wtype)


@attrs.frozen
class Literal(Node):
    """These shouldn't appear in the final AWST.

    They are temporarily constructed during evaluation of sub-expressions, when we encounter
    a literal in the native language (ie Python), and don't have the context to give it a wtype yet

    For example, consider the int literal 42 (randomly selected by fair roll of D100) in the
    following:

        x = algopy.UInt(42)
        x += 42
        y = algopy.BigUInt(42)
        z = algopy.InnerTransactionGroup.sender(42)


    The "type" of 42 in each of these is different.
    For BigUInt, since we know the value at compile time, we wouldn't want to emit a
        push 42
        itob
    Since we can just encode it ourselves and push the result to the stack instead.
    For InnerTransactionGroup.sender - this is actually not of any type, it must end up as a
    literal in the TEAL code itself.
    The type when adding to x should resolve to the UInt64 type, but only because it's in the
    context of an augmented assignment.

    So when we are visiting and arbitrary expression and encounter just a literal expression,
    we need the surrounding context. To avoid having to repeat the transformation of the mypy
    node in every context we could encounter one, we just return this Literal type instead,
    which has no wtype. But it must be resolved before being used at the "outermost level"
    of the current expression/statement, thus this Literal should not end up in the final AWST.

    See also: require_non_literal, for a quick way to ensure that we do indeed have an expression
    in cases where any Literals should have already been resolved.
    """

    value: ConstantValue


@attrs.frozen
class Block(Statement):
    body: Sequence[Statement] = attrs.field(converter=tuple[Statement, ...])

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_block(self)


@attrs.frozen
class IfElse(Statement):
    condition: Expression = attrs.field(validator=[wtype_is_bool])
    if_branch: Block
    else_branch: Block | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_if_else(self)


@attrs.frozen
class WhileLoop(Statement):
    condition: Expression = attrs.field(validator=[wtype_is_bool])
    loop_body: Block

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_while_loop(self)


@attrs.frozen
class BreakStatement(Statement):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_break_statement(self)


@attrs.frozen
class ContinueStatement(Statement):
    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_continue_statement(self)


@attrs.frozen
class AssertStatement(Statement):
    condition: Expression = attrs.field(validator=[wtype_is_bool])
    comment: str | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_assert_statement(self)


@attrs.frozen
class ReturnStatement(Statement):
    value: Expression | None

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_return_statement(self)


def literal_validator(wtype: WType) -> t.Callable[[Node, object, t.Any], None]:
    def validate(node: Node, _attribute: object, value: object) -> None:
        if not isinstance(node, Node):
            raise InternalError(
                f"literal_validator used on type {type(node).__name__}, expected Node"
            )
        if not wtype.is_valid_literal(value):
            raise CodeError(f"Invalid {wtype} value: {value}", node.source_location)

    return validate


@attrs.frozen
class UInt64Constant(Expression):
    wtype: WType = attrs.field(default=wtypes.uint64_wtype, init=False)
    value: int = attrs.field(validator=[literal_validator(wtypes.uint64_wtype)])
    teal_alias: str | None = attrs.field(default=None)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_uint64_constant(self)


@attrs.frozen
class BigUIntConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.biguint_wtype, init=False)
    value: int = attrs.field(validator=[literal_validator(wtypes.biguint_wtype)])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_biguint_constant(self)


@attrs.frozen
class BoolConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)
    value: bool = attrs.field(validator=[literal_validator(wtypes.bool_wtype)])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bool_constant(self)


@attrs.frozen
class BytesConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, init=False)
    value: bytes = attrs.field(validator=[literal_validator(wtypes.bytes_wtype)])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_constant(self)


@attrs.frozen
class AddressConstant(Expression):
    wtype: WType = attrs.field(default=wtypes.address_wtype, init=False)
    value: str = attrs.field(validator=[literal_validator(wtypes.address_wtype)])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_address_constant(self)


class BytesEncoding(enum.StrEnum):
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    method = enum.auto()
    utf8 = enum.auto()


@attrs.frozen
class BytesDecode(Expression):
    value: str  # TODO: validator
    encoding: BytesEncoding
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, init=False)
    # TODO: add evaluation to get bytes

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_decode(self)


@attrs.frozen
class AbiEncode(Expression):
    value: Expression
    wtype: WType

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_abi_encode(self)


@attrs.frozen
class AbiDecode(Expression):
    value: Expression
    wtype: WType

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_abi_decode(self)


@attrs.frozen
class AbiConstant(Expression):
    value: bytes
    wtype: WType
    bytes_encoding: BytesEncoding = attrs.field(default=BytesEncoding.base16)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_abi_constant(self)


@attrs.frozen
class NewAbiArray(Expression):
    elements: tuple[Expression, ...] = attrs.field()
    wtype: wtypes.AbiDynamicArray | wtypes.AbiStaticArray

    @elements.validator
    def check(self, _attribute: object, value: tuple[Expression, ...]) -> None:
        if any(expr.wtype != self.wtype.element_type for expr in value):
            raise ValueError(
                f"All array elements should have array type: {self.wtype.element_type}"
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_new_abi_array(self)


CompileTimeConstantExpression: t.TypeAlias = (
    UInt64Constant | BigUIntConstant | BoolConstant | BytesConstant | AddressConstant | BytesDecode
)


@attrs.define
class IntrinsicCall(Expression):
    op_code: str
    immediates: Sequence[str | int] = attrs.field(default=(), converter=tuple[str | int, ...])
    stack_args: Sequence[Expression] = attrs.field(default=(), converter=tuple[Expression, ...])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_intrinsic_call(self)

    @classmethod
    def bytes_len(cls, expr: Expression, source_location: SourceLocation) -> t.Self:
        if expr.wtype != wtypes.bytes_wtype:
            raise ValueError("Expression for bytes_len must have wtype of bytes")
        return cls(
            source_location=source_location,
            op_code="len",
            stack_args=[expr],
            wtype=wtypes.uint64_wtype,
        )


def lvalue_expr_validator(_instance: object, _attribute: object, value: Expression) -> None:
    if not value.wtype.lvalue:
        raise CodeError(
            f'expression with type "{value.wtype}" can not be assigned to a variable',
            value.source_location,
        )


@attrs.frozen
class TupleExpression(Expression):
    items: Sequence[Expression] = attrs.field(converter=tuple[Expression, ...])
    wtype: wtypes.WTuple

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_tuple_expression(self)


@attrs.frozen(init=False)
class TupleItemExpression(Expression):
    """Represents tuple element access.

    Note: this is its own item (vs IndexExpression) for two reasons:
    1. It's not a valid lvalue (tuples are immutable)
    2. The index must always be a literal
    """

    base: Expression
    index: int

    def __init__(self, base: Expression, index: int, source_location: SourceLocation) -> None:
        base_wtype = base.wtype
        if not isinstance(base_wtype, wtypes.WTuple):
            raise InternalError(
                f"Tuple item expression should be for a tuple type, got {base_wtype}",
                source_location,
            )
        try:
            wtype = base_wtype.types[index]
        except IndexError as ex:
            raise InternalError("invalid index into tuple expression", source_location) from ex
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


@attrs.frozen
class FieldExpression(Expression):
    base: Expression
    name: str

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_field_expression(self)


@attrs.frozen
class IndexExpression(Expression):
    base: Expression
    index: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_index_expression(self)


@attrs.frozen
class SliceExpression(Expression):
    base: Expression

    begin_index: Expression | None
    end_index: Expression | None

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_slice_expression(self)


@attrs.frozen
class AppStateExpression(Expression):
    key: bytes
    key_encoding: BytesEncoding

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_app_state_expression(self)


@attrs.frozen
class AppAccountStateExpression(Expression):
    key: bytes
    key_encoding: BytesEncoding
    account: Expression = attrs.field(
        validator=[expression_has_wtype(wtypes.address_wtype, wtypes.uint64_wtype)]
    )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_app_account_state_expression(self)


@attrs.frozen(init=False)
class TemporaryVariable(Expression):
    _source: Expression  # this is stored here only to ensure equality etc function correctly

    def __init__(self, source: Expression):
        self.__attrs_init__(
            source=source,
            source_location=source.source_location,
            wtype=source.wtype,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_temporary_variable(self)


@attrs.frozen
class ReinterpretCast(Expression):
    """Convert an expression to an AVM equivalent type.

    Note: the validation of this isn't done until IR construction"""

    expr: Expression

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_reinterpret_cast(self)


# Expression types that are valid on the left hand side of assignment *statements*
# Note that some of these can be recursive/nested, eg:
# obj.field[index].another_field = 123
Lvalue = (
    VarExpression
    | FieldExpression
    | IndexExpression
    | TupleExpression
    | AppStateExpression
    | AppAccountStateExpression
    | TemporaryVariable
    | ReinterpretCast
)


@attrs.frozen
class NewArray(Expression):
    elements: tuple[Expression, ...] = attrs.field()
    wtype: wtypes.WArray

    @elements.validator
    def check(self, _attribute: object, value: tuple[Expression, ...]) -> None:
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

    def __attrs_post_init__(self) -> None:
        if self.true_expr.wtype != self.false_expr.wtype:
            raise ValueError(
                f"true and false expressions of conditional have differing types:"
                f" {self.true_expr.wtype} and {self.false_expr.wtype}"
            )

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
    value: Expression = attrs.field(validator=[lvalue_expr_validator])

    def __attrs_post_init__(self) -> None:
        if self.value.wtype != self.target.wtype:
            raise CodeError(
                f"Assignment target type {self.target.wtype}"
                f" differs from expression value type {self.value.wtype}",
                self.source_location,
            )

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
    value: Expression = attrs.field(validator=[lvalue_expr_validator])

    def __init__(self, value: Expression, target: Lvalue, source_location: SourceLocation):
        if isinstance(target, TupleExpression):
            raise CodeError(
                "Tuple unpacking in assignment expressions is not supported",
                target.source_location,
            )
        if value.wtype != target.wtype:
            raise CodeError(
                f"Assignment target type {target.wtype}"
                f" differs from expression value type {value.wtype}",
                source_location,
            )
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
    wtypes.uint64_wtype, wtypes.biguint_wtype, wtypes.bool_wtype
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


bytes_comparable = expression_has_wtype(wtypes.bytes_wtype, wtypes.address_wtype)


@attrs.frozen
class BytesComparisonExpression(Expression):
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    lhs: Expression = attrs.field(validator=[bytes_comparable])
    operator: EqualityComparison
    rhs: Expression = attrs.field(validator=[bytes_comparable])

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_bytes_comparison_expression(self)


@attrs.frozen
class ContractReference:
    module_name: str
    class_name: str

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.class_name))


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


@attrs.frozen
class SubroutineCallExpression(Expression):
    target: FreeSubroutineTarget | InstanceSubroutineTarget | BaseClassSubroutineTarget
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
    pow = "**"  # noqa: A003
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


@attrs.frozen
class UInt64UnaryOperation(Expression):
    op: UInt64UnaryOperator
    expr: Expression = attrs.field(validator=[wtype_is_uint64])
    wtype: WType = attrs.field(default=wtypes.uint64_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_uint64_unary_operation(self)


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
    left: Expression = attrs.field(validator=[wtype_is_bytes])
    op: BytesBinaryOperator
    right: Expression = attrs.field(validator=[wtype_is_bytes])
    wtype: WType = attrs.field(default=wtypes.bytes_wtype, init=False)

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
class Contains(Expression):
    item: Expression
    sequence: Expression
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    def __attrs_post_init__(self) -> None:
        if self.sequence.wtype == wtypes.bytes_wtype:
            raise InternalError(
                "Use IsSubstring for 'in' or 'not in' checks with Bytes", self.source_location
            )
        # TODO: this type handling here probably isn't scalable
        if isinstance(self.sequence.wtype, wtypes.WArray):
            if self.sequence.wtype.element_type != self.item.wtype:
                raise CodeError(
                    f"array element type {self.sequence.wtype.element_type}"
                    f" differs from {self.item.wtype}",
                    self.source_location,
                )
        elif isinstance(self.sequence.wtype, wtypes.WTuple):
            if self.item.wtype not in self.sequence.wtype.types:
                raise CodeError(
                    f"{self.sequence.wtype} does not have element with type {self.item.wtype}",
                    self.source_location,
                )
        else:
            raise CodeError(
                f"Type doesn't support in/not in checks: {self.sequence.wtype}",
                self.source_location,
            )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_contains_expression(self)


wtype_is_bytes = expression_has_wtype(wtypes.bytes_wtype)


@attrs.frozen
class IsSubstring(Expression):
    item: Expression = attrs.field(validator=[wtype_is_bytes])
    sequence: Expression = attrs.field(validator=[wtype_is_bytes])
    wtype: WType = attrs.field(default=wtypes.bool_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_is_substring(self)


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
    target: Lvalue = attrs.field(validator=[wtype_is_bytes])
    op: BytesBinaryOperator
    value: Expression = attrs.field(validator=[wtype_is_bytes])

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
        wtype = wtypes.WTuple.from_types([wtypes.uint64_wtype, item_wtype])
        self.__attrs_init__(
            expr=expr,
            source_location=source_location,
            wtype=wtype,
        )

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_enumeration(self)


@attrs.frozen
class ForInLoop(Statement):
    sequence: Expression | Range
    items: Lvalue  # item variable(s)
    loop_body: Block

    def accept(self, visitor: StatementVisitor[T]) -> T:
        return visitor.visit_for_in_loop(self)


@attrs.frozen
class NewStruct(Expression):
    args: tuple[CallArg, ...] = attrs.field()
    wtype: wtypes.WStructType

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_new_struct(self)


@attrs.frozen
class ArrayAppend(Expression):
    array: Expression
    element: Expression
    wtype: WType = attrs.field(default=wtypes.void_wtype, init=False)

    def accept(self, visitor: ExpressionVisitor[T]) -> T:
        return visitor.visit_array_append(self)


@attrs.frozen
class ModuleStatement(Node, ABC):
    name: str

    @abstractmethod
    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        ...


@attrs.frozen
class ConstantDeclaration(ModuleStatement):
    value: ConstantValue

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_constant_declaration(self)


@attrs.frozen
class SubroutineArgument(Node):
    name: str
    wtype: WType


@attrs.frozen
class ABIMethodConfig(Node):
    name_override: str | None
    # TODO: the rest


@attrs.frozen
class Function(ModuleStatement, ABC):
    module_name: str
    args: Sequence[SubroutineArgument] = attrs.field(converter=tuple[SubroutineArgument, ...])
    return_type: WType
    body: Block
    docstring: str | None

    @property
    @abstractmethod
    def full_name(self) -> str:
        ...


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
    abimethod_config: ABIMethodConfig | None

    @property
    def full_name(self) -> str:
        return ".".join((self.module_name, self.class_name, self.name))

    def accept(self, visitor: ModuleStatementVisitor[T]) -> T:
        return visitor.visit_contract_method(self)


@enum.unique
class AppStateKind(enum.Enum):
    app_global = enum.auto()
    account_local = enum.auto()


@attrs.frozen
class AppStateDefinition(Node):
    member_name: str
    kind: AppStateKind
    key: bytes
    key_encoding: BytesEncoding
    storage_wtype: WType


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
    app_state: Sequence[AppStateDefinition] = attrs.field(converter=tuple[AppStateDefinition, ...])
    docstring: str | None
    # note: important that symtable comes last so default factory has access to all other fields
    symtable: Mapping[str, ContractMethod | AppStateDefinition] = attrs.field(init=False)

    @symtable.default
    def _symtable_factory(self) -> Mapping[str, ContractMethod | AppStateDefinition]:
        all_subs = [
            self.init,
            self.approval_program,
            self.clear_program,
            *self.subroutines,
        ]
        subs_by_name = {sub.name: sub for sub in all_subs if sub is not None}
        state_by_name = {state.member_name: state for state in self.app_state}
        return {
            **subs_by_name,
            **state_by_name,
        }

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
            if init.abimethod_config is not None:
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
            if approval.abimethod_config:
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
            if clear.abimethod_config:
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


@attrs.frozen(slots=False)
class Module:
    name: str
    source_file_path: str
    docstring: str | None
    body: Sequence[ModuleStatement] = attrs.field(converter=tuple[ModuleStatement, ...])

    @cached_property
    def symtable(self) -> Mapping[str, ModuleStatement]:
        return {stmt.name: stmt for stmt in self.body}
