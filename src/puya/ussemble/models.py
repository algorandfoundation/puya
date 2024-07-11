import abc
import typing
from collections.abc import Mapping, Sequence

import attrs

from puya.errors import InternalError
from puya.parse import SourceLocation
from puya.ussemble.visitor import AVMVisitor
from puya.utils import valid_bytes, valid_int64

T = typing.TypeVar("T")

MAX_CONSTANT_REFERENCE = 255


@attrs.frozen
class Node(abc.ABC):
    source_location: SourceLocation | None = attrs.field(eq=False)

    @abc.abstractmethod
    def accept(self, visitor: AVMVisitor[T]) -> T: ...


def _valid_uint64(node: Node, _attribute: object, value: int) -> None:
    if not valid_int64(value):
        raise InternalError(
            "Invalid UInt64 value",
            node.source_location,
        )


def _valid_bytes(node: Node, _attribute: object, value: bytes) -> None:
    if not valid_bytes(value):
        raise InternalError("Invalid Bytes value", node.source_location)


def _valid_ref(node: Node, _attribute: object, value: int) -> None:
    if value < 0 or value > MAX_CONSTANT_REFERENCE:
        raise InternalError(
            "Invalid constant reference",
            node.source_location,
        )


@attrs.frozen
class AVMOp(Node, abc.ABC):
    op_code: str


@attrs.frozen
class IntBlock(AVMOp):
    op_code: str = attrs.field(default="intcblock", init=False)
    constants: Mapping[int, int]

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_int_block(self)


@attrs.frozen
class BytesBlock(AVMOp):
    op_code: str = attrs.field(default="bytecblock", init=False)
    constants: Mapping[bytes, int]

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_bytes_block(self)


@attrs.frozen
class IntC(AVMOp):
    op_code: str = attrs.field(default="intc", init=False)
    index: int = attrs.field(validator=_valid_ref)

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_intc(self)


@attrs.frozen
class PushInt(AVMOp):
    op_code: str = attrs.field(default="pushint", init=False)
    value: int = attrs.field(validator=_valid_uint64)

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_push_int(self)


@attrs.frozen
class PushInts(AVMOp):
    op_code: str = attrs.field(default="pushints", init=False)
    values: list[int] = attrs.field(validator=attrs.validators.deep_iterable(_valid_uint64))

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_push_ints(self)


@attrs.frozen
class BytesC(AVMOp):
    op_code: str = attrs.field(default="bytec", init=False)
    index: int = attrs.field(validator=_valid_ref)

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_bytesc(self)


@attrs.frozen
class PushBytes(AVMOp):
    op_code: str = attrs.field(default="pushbytes", init=False)
    value: bytes = attrs.field(validator=_valid_bytes)

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_push_bytes(self)


@attrs.frozen
class PushBytess(AVMOp):
    op_code: str = attrs.field(default="pushbytess", init=False)
    values: list[bytes] = attrs.field(validator=attrs.validators.deep_iterable(_valid_bytes))

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_push_bytess(self)


@attrs.frozen
class Label(Node):
    name: str
    source_location: None = attrs.field(default=None, init=False, eq=False)

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_label(self)


@attrs.frozen
class Jump(AVMOp):
    label: Label

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_jump(self)


@attrs.frozen
class MultiJump(AVMOp):
    labels: list[Label]

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_multi_jump(self)


@attrs.frozen
class Intrinsic(AVMOp):
    immediates: Sequence[int | str]

    def accept(self, visitor: AVMVisitor[T]) -> T:
        return visitor.visit_intrinsic(self)
