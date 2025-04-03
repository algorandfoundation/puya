from __future__ import annotations

import abc
import enum
import typing
from collections.abc import Sequence

import attrs
import typing_extensions

from puya import log
from puya.awst.nodes import (
    BinaryBooleanOperator,
    Expression,
    Lvalue,
    Statement,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import invert_ordered_binary_op
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.models import ConstantValue

logger = log.get_logger(__name__)


@enum.unique
class BuilderComparisonOp(enum.StrEnum):
    eq = "=="
    ne = "!="
    lt = "<"
    lte = "<="
    gt = ">"
    gte = ">="

    def reversed(self) -> BuilderComparisonOp:
        return BuilderComparisonOp(invert_ordered_binary_op(self.value))


@enum.unique
class BuilderUnaryOp(enum.StrEnum):
    positive = "+"
    negative = "-"
    bit_invert = "~"


@enum.unique
class BuilderBinaryOp(enum.StrEnum):
    add = "+"
    sub = "-"
    mult = "*"
    div = "/"
    floor_div = "//"
    mod = "%"
    pow = "**"
    mat_mult = "@"
    lshift = "<<"
    rshift = ">>"
    bit_or = "|"
    bit_xor = "^"
    bit_and = "&"


class NodeBuilder(abc.ABC):
    def __init__(self, location: SourceLocation):
        self.source_location: typing.Final = location

    @property
    @abc.abstractmethod
    def pytype(self) -> pytypes.PyType | None: ...

    @abc.abstractmethod
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        """Handle self.name"""

    @abc.abstractmethod
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        """Handle boolean-ness evaluation, possibly inverted (ie "not" unary operator)"""


class CallableBuilder(NodeBuilder, abc.ABC):
    @abc.abstractmethod
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        """Handle self(args...)"""


_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class InstanceBuilder(NodeBuilder, typing.Generic[_TPyType_co], abc.ABC):
    @typing.override
    @property
    @abc.abstractmethod
    def pytype(self) -> _TPyType_co: ...

    @abc.abstractmethod
    def resolve(self) -> Expression:
        """Produce an expression for use as an intermediary"""

    @abc.abstractmethod
    def resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder:
        """For use prior to calling resolve(), when a known type is expected,
        and implicit conversion is possible without breaking semantic compatibility.

        Primarily, this would be as an argument to an algopy function or class, or as an
        operand to a binary operator with an algopy-typed object.

        When implementing, this function should return self if there are no literals to convert,
        or if the literals are not expected to be homogenous (e.g. in the general case of a tuple
        with literals)"""

    @abc.abstractmethod
    def try_resolve_literal(self, converter: TypeBuilder) -> InstanceBuilder | None:
        """Similar to resolve_literal, but in the case where a conversion is possible but the
        literal values are the wrong type, don't produce any errors and return None instead.

        If no conversion is necessary (ie no literals or it's not meaningful to convert literals
        this way, such as a tuple with literals), just return the current instance.
        """

    @abc.abstractmethod
    def resolve_lvalue(self) -> Lvalue:
        """Produce an expression for the target of an assignment"""

    @abc.abstractmethod
    def delete(self, location: SourceLocation) -> Statement:
        """Handle del self"""

    @abc.abstractmethod
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> InstanceBuilder:
        """Handle {op} self"""

    @abc.abstractmethod
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> InstanceBuilder:
        """Handle self {op} other"""

    @abc.abstractmethod
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> InstanceBuilder:
        """Handle self {op} other"""

    @abc.abstractmethod
    def bool_binary_op(
        self, other: InstanceBuilder, op: BinaryBooleanOperator, location: SourceLocation
    ) -> InstanceBuilder:
        """Handle self and/or other"""
        from puyapy.awst_build.eb.binary_bool_op import BinaryBoolOpBuilder

        return BinaryBoolOpBuilder(left=self, right=other, op=op, location=location)

    @abc.abstractmethod
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        """Handle self {op}= rhs"""

    @abc.abstractmethod
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        """Handle item in self"""
        from puyapy.awst_build.eb._utils import dummy_value

        logger.error("expression is not iterable", location=self.source_location)
        return dummy_value(pytypes.BoolType, location)

    @abc.abstractmethod
    def iterate(self) -> Expression:
        """Produce target of ForInLoop"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def iterable_item_type(self) -> pytypes.PyType:
        """The type of the item if this expression is iterable"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        """Handle self[index]"""
        raise CodeError("expression is not a collection", location)

    @abc.abstractmethod
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        """Handle self[begin_index:end_index:stride]"""
        raise CodeError("expression is not a collection", location)

    @abc.abstractmethod
    def to_bytes(self, location: SourceLocation) -> Expression:
        """Handle conversion/cast to bytes, if possible"""

    @abc.abstractmethod
    def single_eval(self) -> InstanceBuilder:
        """wrap any underlying expressions etc. (if applicable) to avoid multiple evaluations"""


class StaticSizedCollectionBuilder(NodeBuilder, abc.ABC):
    @abc.abstractmethod
    def iterate_static(self) -> Sequence[InstanceBuilder]: ...


class LiteralBuilder(InstanceBuilder, abc.ABC):
    @property
    @abc.abstractmethod
    def value(self) -> ConstantValue: ...

    @typing.override
    @abc.abstractmethod
    def unary_op(self, op: BuilderUnaryOp, location: SourceLocation) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def member_access(self, name: str, location: SourceLocation) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def compare(
        self, other: InstanceBuilder, op: BuilderComparisonOp, location: SourceLocation
    ) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def binary_op(
        self,
        other: InstanceBuilder,
        op: BuilderBinaryOp,
        location: SourceLocation,
        *,
        reverse: bool,
    ) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def index(self, index: InstanceBuilder, location: SourceLocation) -> LiteralBuilder: ...

    @typing.override
    @abc.abstractmethod
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> LiteralBuilder: ...


# TODO: separate interface from implementation
class TypeBuilder(CallableBuilder, typing.Generic[_TPyType_co], abc.ABC):
    def __init__(self, pytype: _TPyType_co, location: SourceLocation):
        super().__init__(location)
        self._pytype = pytype

    @typing.final
    @typing.override
    @property
    def pytype(self) -> pytypes.TypeType:
        return pytypes.TypeType(self._pytype)

    @typing.final
    def produces(self) -> _TPyType_co:
        return self._pytype

    @typing.final
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder:
        from puyapy.awst_build.eb._utils import dummy_value

        result = self.try_convert_literal(literal, location)
        if result is not None:
            return result
        logger.error(
            f"can't covert literal to {self.produces()}", location=literal.source_location
        )
        return dummy_value(self.produces(), location)

    def try_convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder | None:
        """
        If the type of `literal.value` is correct, return a new instance, otherwise return `None`.
        If the value is out of range or otherwise invalid, an error is logged,
        but an instance is still returned.
        """
        return None

    @typing.override
    @typing.final
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        from puyapy.awst_build.eb._utils import constant_bool_and_error

        return constant_bool_and_error(value=True, location=location, negate=negate)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        raise CodeError(f"unrecognised member {name!r} of type '{self._pytype}'", location)


@attrs.frozen(kw_only=True)
class StorageProxyConstructorArgs:
    key: Expression | None
    key_arg_name: str
    description: str | None
    initial_value: InstanceBuilder | None = None


class StorageProxyConstructorResult(
    InstanceBuilder[pytypes.StorageProxyType | pytypes.StorageMapProxyType], abc.ABC
):
    @property
    @abc.abstractmethod
    def args(self) -> StorageProxyConstructorArgs: ...
