from __future__ import annotations

import abc
import typing as t
from functools import cached_property

import attrs

from puya.codegen.utils import format_bytes

if t.TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from puya.avm_type import AVMType
    from puya.codegen.teal import TealOp
    from puya.codegen.visitor import MIRVisitor
    from puya.ir.types_ import AVMBytesEncoding
    from puya.parse import SourceLocation
_T = t.TypeVar("_T")


@attrs.frozen(kw_only=True, eq=False, str=False)
class BaseOp(abc.ABC):
    comment: str | None = attrs.field(default=None)
    source_location: SourceLocation | None = attrs.field(default=None)

    @abc.abstractmethod
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        ...


@attrs.frozen(eq=False)
class PushInt(BaseOp):
    value: int | str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_push_int(self)

    def __str__(self) -> str:
        return f"int {self.value}"


@attrs.frozen(eq=False)
class PushBytes(BaseOp):
    value: bytes
    encoding: AVMBytesEncoding

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_push_bytes(self)

    def __str__(self) -> str:
        return f"byte {format_bytes(self.value, self.encoding)}"


@attrs.frozen(eq=False)
class PushAddress(BaseOp):
    value: str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_push_address(self)

    def __str__(self) -> str:
        return f'addr "{self.value}"'


@attrs.frozen(eq=False)
class PushMethod(BaseOp):
    value: str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_push_method(self)

    def __str__(self) -> str:
        return f"method {self.value}"


@attrs.frozen(eq=False)
class Comment(BaseOp):
    comment: str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_comment(self)

    def __str__(self) -> str:
        return f"// {self.comment}"


@attrs.frozen(kw_only=True, eq=False)
class MemoryOp(BaseOp, abc.ABC):
    """An op that is concerned with manipulating memory"""


@attrs.frozen(kw_only=True, eq=False)
class StoreOp(MemoryOp, abc.ABC):
    """An op for storing values"""

    local_id: str
    atype: AVMType


@attrs.frozen(kw_only=True, eq=False)
class LoadOp(MemoryOp, abc.ABC):
    """An op for loading values"""

    local_id: str
    atype: AVMType


@attrs.frozen(eq=False)
class StoreVirtual(StoreOp):
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_virtual(self)

    def __str__(self) -> str:
        return f"store {self.local_id}"


@attrs.frozen(eq=False)
class LoadVirtual(LoadOp):
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_virtual(self)

    def __str__(self) -> str:
        return f"load {self.local_id}"


@attrs.frozen(eq=False, kw_only=True)
class StoreLStack(StoreOp):
    cover: int = attrs.field(validator=attrs.validators.ge(0))
    copy: bool = attrs.field(default=True)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_l_stack(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"store {self.local_id} to l-stack {copy}"


@attrs.frozen(eq=False)
class LoadLStack(LoadOp):
    copy: bool = attrs.field(default=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_l_stack(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"load {self.local_id} from l-stack {copy}"


@attrs.frozen(eq=False)
class StoreXStack(StoreOp):
    copy: bool = attrs.field(default=True)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_x_stack(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"store {self.local_id} to x-stack {copy}"


@attrs.frozen(eq=False)
class LoadXStack(LoadOp):
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_x_stack(self)

    def __str__(self) -> str:
        return f"load {self.local_id} from x-stack"


@attrs.frozen(eq=False)
class StoreFStack(StoreOp):
    insert: bool = attrs.field(default=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_f_stack(self)

    def __str__(self) -> str:
        return f"store {self.local_id} to f-stack"


@attrs.frozen(eq=False)
class LoadFStack(LoadOp):
    move: bool = attrs.field(default=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_f_stack(self)

    def __str__(self) -> str:
        return f"load {self.local_id} from f-stack"


@attrs.frozen(eq=False)
class LoadParam(LoadOp):
    index: int

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_param(self)

    def __str__(self) -> str:
        return f"load {self.local_id} from parameters"


@attrs.frozen(eq=False)
class StoreParam(StoreOp):
    index: int
    copy: bool = attrs.field(default=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_param(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"store {self.local_id} to parameters {copy}"


@attrs.frozen(eq=False)
class Pop(MemoryOp):
    n: int

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_pop(self)

    def __str__(self) -> str:
        return f"pop {self.n}"


@attrs.frozen(eq=False, init=False)
class VirtualStackOp(BaseOp):
    original: Sequence[MemoryOp]
    replacement: Sequence[TealOp] | None
    """Optional series of ops that leave the stack state in the same order as original, but
    with less ops"""

    def __init__(
        self,
        original: MemoryOp | Sequence[MemoryOp],
        replacement: Sequence[TealOp] | None = None,
    ):
        original = [original] if isinstance(original, MemoryOp) else original
        srcs = list(filter(None, (x.source_location for x in original)))
        source_location: SourceLocation | None = None
        if srcs:
            source_location, *others = srcs
            for other in others:
                source_location += other
        self.__attrs_init__(
            original=original,
            replacement=replacement,
            source_location=source_location,
        )

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_virtual_stack(self)

    def __str__(self) -> str:
        if len(self.original) > 1:
            return f"virtual: {len(self.original)} ops"
        return f"virtual: {'; '.join(map(str, self.original))}"


@attrs.frozen(eq=False)
class Proto(BaseOp):
    parameters: int
    returns: int

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_proto(self)

    def __str__(self) -> str:
        return f"proto {self.parameters} {self.returns}"


def _validate_allocate(
    instance: Allocate,
    _attr: attrs.Attribute[int] | attrs.Attribute[Sequence[str]],
    _: int | Sequence[str],
) -> None:
    if len(instance.allocate_on_entry) != instance.num_uints + instance.num_bytes:
        raise ValueError("num_uints + num_bytes must equal len(allocate_on_entry)")


@attrs.frozen(eq=False)
class Allocate(BaseOp):
    allocate_on_entry: Sequence[str] = attrs.field(
        validator=[attrs.validators.min_len(1), _validate_allocate]
    )
    """List of bytes variables, followed by uint64 variables to allocate at the start
    of a call frame"""
    num_bytes: int = attrs.field(validator=[attrs.validators.ge(0), _validate_allocate])
    num_uints: int = attrs.field(validator=[attrs.validators.ge(0), _validate_allocate])

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_allocate(self)

    def __str__(self) -> str:
        return f"allocate {len(self.allocate_on_entry)} to stack"


@attrs.frozen(eq=False)
class CallSub(BaseOp):
    target: str
    parameters: int
    returns: int

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_callsub(self)

    def __str__(self) -> str:
        return f"callsub {self.target}"


@attrs.frozen(eq=False)
class RetSub(MemoryOp):
    returns: int
    f_stack_size: int = attrs.field(default=0)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_retsub(self)

    def __str__(self) -> str:
        return "retsub"


@attrs.frozen(eq=False)
class IntrinsicOp(BaseOp):
    """An Op that does something other than just manipulating memory"""

    # TODO: use enum values for these ops
    op_code: str
    consumes: int
    produces: int | Sequence[str]
    immediates: Sequence[str | int] = attrs.field(default=(), converter=tuple[str | int, ...])

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_intrinsic(self)

    def __str__(self) -> str:
        teal = [self.op_code, *map(str, self.immediates)]
        if self.comment:
            # TODO: determine if the comment is user defined or not
            # if not user then self.include_op_desc should be respected
            # e.g. consider assert comments
            teal += ("//", self.comment)
        return " ".join(teal)


@attrs.define(eq=False, repr=False)
class MemoryBasicBlock:
    block_name: str
    ops: list[BaseOp]
    predecessors: list[str]
    successors: list[str]
    source_location: SourceLocation
    # TODO: move this somewhere else?
    x_stack_in: Sequence[str] | None = None
    x_stack_out: Sequence[str] | None = None
    f_stack_in: Sequence[str] = attrs.field(factory=list)

    def __repr__(self) -> str:
        return self.block_name


@attrs.frozen(kw_only=True)
class Parameter:
    local_id: str
    atype: AVMType


@attrs.frozen(str=False)
class Signature:
    name: str
    parameters: Sequence[Parameter]
    returns: Sequence[AVMType]

    def __str__(self) -> str:
        params = ", ".join(f"{p.local_id}: {p.atype.name}" for p in self.parameters)
        returns = ", ".join(str(r.name) for r in self.returns)
        return f"{self.name}({params}) -> {returns or 'void'}:"


@attrs.define(slots=False)
class MemorySubroutine:
    """A lower form of IR that is concerned with memory assignment (both stack and scratch)"""

    is_main: bool
    signature: Signature
    preamble: MemoryBasicBlock
    body: Sequence[MemoryBasicBlock]

    @property
    def all_blocks(self) -> Iterable[MemoryBasicBlock]:
        if self.preamble.ops:
            yield self.preamble
        yield from self.body

    @cached_property
    def block_map(self) -> Mapping[str, MemoryBasicBlock]:
        return {b.block_name: b for b in self.all_blocks}

    def get_block(self, block_name: str) -> MemoryBasicBlock:
        return self.block_map[block_name]
