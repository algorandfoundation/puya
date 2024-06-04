from __future__ import annotations

import abc
import enum
import typing

import mypy.nodes
import typing_extensions

from puya.awst.nodes import ConstantValue, ContractReference, Expression, Lvalue, Range, Statement
from puya.awst_build import pytypes
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.errors import CodeError
from puya.parse import SourceLocation

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Sequence

Iteration: typing.TypeAlias = Expression | Range


@enum.unique
class BuilderComparisonOp(enum.StrEnum):
    eq = "=="
    ne = "!="
    lt = "<"
    lte = "<="
    gt = ">"
    gte = ">="


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
        self.source_location = location

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
        arg_kinds: list[mypy.nodes.ArgKind],
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
    def augmented_assignment(
        self, op: BuilderBinaryOp, rhs: InstanceBuilder, location: SourceLocation
    ) -> Statement:
        """Handle self {op}= rhs"""

    @abc.abstractmethod
    def contains(self, item: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        """Handle item in self"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def iterate(self) -> Iteration:
        """Produce target of ForInLoop"""
        raise CodeError("expression is not iterable", self.source_location)

    @abc.abstractmethod
    def index(self, index: InstanceBuilder, location: SourceLocation) -> InstanceBuilder:
        """Handle self[index]"""
        raise CodeError("expression is not a collection", self.source_location)

    @abc.abstractmethod
    def slice_index(
        self,
        begin_index: InstanceBuilder | None,
        end_index: InstanceBuilder | None,
        stride: InstanceBuilder | None,
        location: SourceLocation,
    ) -> InstanceBuilder:
        """Handle self[begin_index:end_index:stride]"""
        raise CodeError("expression is not a collection", self.source_location)

    @abc.abstractmethod
    def to_bytes(self, location: SourceLocation) -> Expression:
        """Handle conversion/cast to bytes, if possible"""


class LiteralBuilder(InstanceBuilder, abc.ABC):
    @property
    @abc.abstractmethod
    def value(self) -> ConstantValue: ...


class LiteralConverter(NodeBuilder, abc.ABC):
    @property
    @abc.abstractmethod
    def handled_types(self) -> Collection[pytypes.PyType]: ...

    @abc.abstractmethod
    def convert_literal(
        self, literal: LiteralBuilder, location: SourceLocation
    ) -> InstanceBuilder: ...


class StorageProxyConstructorResult(
    InstanceBuilder[pytypes.StorageProxyType | pytypes.StorageMapProxyType], abc.ABC
):
    @property
    @abc.abstractmethod
    def initial_value(self) -> Expression | None: ...

    @abc.abstractmethod
    def build_definition(
        self,
        member_name: str,
        defined_in: ContractReference,
        typ: pytypes.PyType,
        location: SourceLocation,
    ) -> AppStorageDeclaration: ...
