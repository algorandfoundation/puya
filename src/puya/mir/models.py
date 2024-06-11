from __future__ import annotations

import abc
import typing as t
from functools import cached_property

import attrs

from puya.avm_type import AVMType
from puya.errors import InternalError
from puya.ir.utils import format_bytes

if t.TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from puya.ir.types_ import AVMBytesEncoding
    from puya.mir.visitor import MIRVisitor
    from puya.parse import SourceLocation

_T = t.TypeVar("_T")


@attrs.frozen(kw_only=True, eq=False, str=False)
class BaseOp(abc.ABC):
    comment: str | None = None
    source_location: SourceLocation | None = None

    @abc.abstractmethod
    def accept(self, visitor: MIRVisitor[_T]) -> _T: ...


@attrs.frozen(eq=False)
class Int(BaseOp):
    value: int | str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_int(self)

    def __str__(self) -> str:
        return f"int {self.value}"


@attrs.frozen(eq=False)
class Byte(BaseOp):
    value: bytes
    encoding: AVMBytesEncoding

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_byte(self)

    def __str__(self) -> str:
        return f"byte {format_bytes(self.value, self.encoding)}"


@attrs.frozen(eq=False)
class TemplateVar(BaseOp):
    name: str
    atype: AVMType = attrs.field()
    op_code: str = attrs.field(init=False)

    @op_code.default
    def _default_opcode(self) -> str:
        match self.atype:
            case AVMType.bytes:
                return "byte"
            case AVMType.uint64:
                return "int"
            case _:
                raise InternalError(
                    f"Unsupported atype for TemplateVar: {self.atype}", self.source_location
                )

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_template_var(self)

    def __str__(self) -> str:
        return f"{self.op_code} {self.name}"


@attrs.frozen(eq=False)
class Address(BaseOp):
    value: str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_address(self)

    def __str__(self) -> str:
        return f'addr "{self.value}"'


@attrs.frozen(eq=False)
class Method(BaseOp):
    value: str

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_method(self)

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
    atype: AVMType = attrs.field()

    @atype.validator
    def _validate_not_any(self, _attribute: object, atype: AVMType) -> None:
        if atype is AVMType.any:
            raise InternalError(f"Register has type any: {self}", self.source_location)


@attrs.frozen(kw_only=True, eq=False)
class LoadOp(MemoryOp, abc.ABC):
    """An op for loading values"""

    local_id: str
    atype: AVMType = attrs.field()

    @atype.validator
    def _validate_not_any(self, _attribute: object, atype: AVMType) -> None:
        if atype is AVMType.any:
            raise InternalError(f"Register has type any: {self}", self.source_location)


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
    copy: bool = True

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_l_stack(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"store {self.local_id} to l-stack {copy}"


@attrs.frozen(eq=False)
class LoadLStack(LoadOp):
    copy: bool = False

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_l_stack(self)

    def __str__(self) -> str:
        copy = "(copy)" if self.copy else "(no copy)"
        return f"load {self.local_id} from l-stack {copy}"


@attrs.frozen(eq=False)
class StoreXStack(StoreOp):
    copy: bool = True

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
    insert: bool = False

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_f_stack(self)

    def __str__(self) -> str:
        return f"store {self.local_id} to f-stack"


@attrs.frozen(eq=False)
class LoadFStack(LoadOp):
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
    copy: bool = False

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


@t.final
@attrs.frozen(eq=False)
class VirtualStackOp(BaseOp):
    """A no-op that manipulates the virtual stack"""

    original: BaseOp
    source_location: SourceLocation | None = attrs.field(init=False)

    @source_location.default
    def _source_location_factory(self) -> SourceLocation | None:
        return self.original.source_location

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_virtual_stack(self)

    def __str__(self) -> str:
        return f"virtual: {self.original}"


@attrs.frozen(eq=False)
class Proto(BaseOp):
    parameters: int
    returns: int

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_proto(self)

    def __str__(self) -> str:
        return f"proto {self.parameters} {self.returns}"


@attrs.frozen(eq=False)
class Allocate(BaseOp):
    bytes_vars: Sequence[str]
    uint64_vars: Sequence[str]

    @property
    def allocate_on_entry(self) -> Sequence[str]:
        return [*self.bytes_vars, *self.uint64_vars]

    @property
    def num_bytes(self) -> int:
        return len(self.bytes_vars)

    @property
    def num_uints(self) -> int:
        return len(self.uint64_vars)

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
    f_stack_size: int = 0

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

    def __attrs_post_init__(self) -> None:
        if self.op_code in ("b", "bz", "bnz", "switch", "match") and not isinstance(
            self, BranchingOp
        ):
            raise InternalError(
                f"Branching op {self.op_code} should map to explicit MIR ops", self.source_location
            )

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


class BranchingOp(IntrinsicOp, abc.ABC):
    @abc.abstractmethod
    def targets(self) -> Sequence[str]: ...


@attrs.frozen(eq=False)
class Branch(BranchingOp):
    op_code: str = attrs.field(default="b", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)
    immediates: Sequence[str] = attrs.field(
        validator=[attrs.validators.min_len(1), attrs.validators.max_len(1)],
        converter=tuple[str, ...],
    )

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.frozen(eq=False)
class BranchNonZero(BranchingOp):
    op_code: str = attrs.field(default="bnz", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)
    immediates: Sequence[str] = attrs.field(
        validator=[attrs.validators.min_len(1), attrs.validators.max_len(1)],
        converter=tuple[str, ...],
    )

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.frozen(eq=False)
class BranchZero(BranchingOp):
    op_code: str = attrs.field(default="bz", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)
    immediates: Sequence[str] = attrs.field(
        validator=[attrs.validators.min_len(1), attrs.validators.max_len(1)],
        converter=tuple[str, ...],
    )

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.frozen(eq=False)
class Switch(BranchingOp):
    op_code: str = attrs.field(default="switch", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)
    immediates: Sequence[str] = attrs.field(converter=tuple[str, ...])

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.frozen(eq=False, init=False)
class Match(BranchingOp):
    op_code: str = attrs.field(default="match", init=False)
    produces: int = attrs.field(default=0, init=False)
    immediates: Sequence[str] = attrs.field(converter=tuple[str, ...])

    def __init__(
        self,
        immediates: Sequence[str],
        comment: str | None = None,
        source_location: SourceLocation | None = None,
    ):
        self.__attrs_init__(
            immediates=immediates,
            consumes=len(immediates) + 1,
            comment=comment,
            source_location=source_location,
        )

    def targets(self) -> Sequence[str]:
        return self.immediates


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
    f_stack_out: Sequence[str] = attrs.field(factory=list)

    def __repr__(self) -> str:
        return self.block_name

    @property
    def entry_stack_height(self) -> int:
        return len(self.f_stack_in) + len(self.x_stack_in or ())

    @property
    def exit_stack_height(self) -> int:
        return len(self.f_stack_out) + len(self.x_stack_out or ())


@attrs.frozen(kw_only=True)
class Parameter:
    name: str
    local_id: str
    atype: AVMType


@attrs.frozen(str=False)
class Signature:
    name: str
    parameters: Sequence[Parameter]
    returns: Sequence[AVMType]

    def __str__(self) -> str:
        params = ", ".join(f"{p.name}: {p.atype.name}" for p in self.parameters)
        returns = ", ".join(str(r.name) for r in self.returns)
        return f"{self.name}({params}) -> {returns or 'void'}:"


@attrs.define
class MemorySubroutine:
    """A lower form of IR that is concerned with memory assignment (both stack and scratch)"""

    is_main: bool
    signature: Signature
    preamble: MemoryBasicBlock
    body: Sequence[MemoryBasicBlock]

    @property
    def all_blocks(self) -> Iterable[MemoryBasicBlock]:
        yield self.preamble
        yield from self.body

    @cached_property
    def block_map(self) -> Mapping[str, MemoryBasicBlock]:
        return {b.block_name: b for b in self.all_blocks}

    def get_block(self, block_name: str) -> MemoryBasicBlock:
        return self.block_map[block_name]


@attrs.define
class Program:
    main: MemorySubroutine
    subroutines: list[MemorySubroutine]

    @property
    def all_subroutines(self) -> Iterator[MemorySubroutine]:
        yield self.main
        yield from self.subroutines
