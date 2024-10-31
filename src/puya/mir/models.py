from __future__ import annotations

import abc
import typing
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
    consumes: int
    """How many values are removed from the top of l-stack
    Does not take into account any manipulations lower in the stack e.g. from Load*Stack"""
    produces: Sequence[str]
    """The local ids that are appended to the l-stack
    Does not take into account any manipulations lower in the stack e.g. from Store*Stack"""

    @abc.abstractmethod
    def accept(self, visitor: MIRVisitor[_T]) -> _T: ...


def _is_single_item(_: object, __: object, value: Sequence[str]) -> None:
    assert len(value) == 1, "expected single item"


@attrs.frozen(eq=False)
class Int(BaseOp):
    value: int | str
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (str(self.value),)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_int(self)

    def __str__(self) -> str:
        return f"int {self.value}"


@attrs.frozen(eq=False)
class Byte(BaseOp):
    value: bytes
    encoding: AVMBytesEncoding
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (format_bytes(self.value, self.encoding),)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_byte(self)

    def __str__(self) -> str:
        return f"byte {format_bytes(self.value, self.encoding)}"


@attrs.frozen(eq=False)
class TemplateVar(BaseOp):
    name: str
    atype: AVMType = attrs.field()
    op_code: typing.Literal["int", "byte"] = attrs.field(init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (self.name,)

    @op_code.default
    def _default_opcode(self) -> typing.Literal["int", "byte"]:
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
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (f"Address({self.value})",)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_address(self)

    def __str__(self) -> str:
        return f'addr "{self.value}"'


@attrs.frozen(eq=False)
class Method(BaseOp):
    value: str
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (f"Method({self.value})",)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_method(self)

    def __str__(self) -> str:
        return f"method {self.value}"


@attrs.frozen(eq=False)
class Comment(BaseOp):
    comment: str
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

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
class AbstractStore(StoreOp):
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_abstract_store(self)

    def __str__(self) -> str:
        return f"v-store {self.local_id}"


@attrs.frozen(eq=False)
class AbstractLoad(LoadOp):
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (self.local_id,)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_abstract_load(self)

    def __str__(self) -> str:
        return f"v-load {self.local_id}"


@attrs.frozen(eq=False, kw_only=True)
class StoreLStack(StoreOp):
    depth: int = attrs.field(validator=attrs.validators.ge(0))
    copy: bool
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field()

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (f"{self.local_id} (copy)",) if self.copy else ()

    @produces.validator
    def _validate_produces(self, _: object, value: Sequence[str]) -> None:
        assert len(value) == (1 if self.copy else 0), "invalid produces size"

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_l_stack(self)

    def __str__(self) -> str:
        op = "l-store-copy" if self.copy else "l-store"
        return f"{op} {self.local_id} {self.depth}"


@attrs.frozen(eq=False)
class LoadLStack(LoadOp):
    copy: bool
    consumes: int = attrs.field(init=False, default=0)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)
    # depth can only be defined after koopmans pass and dead store removal
    depth: int | None = None

    @produces.default
    def _produces(self) -> Sequence[str]:
        produces = self.local_id
        if self.copy:
            produces += " (copy)"
        return (produces,)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_l_stack(self)

    def __str__(self) -> str:
        depth = "" if self.depth is None else f" {self.depth}"
        op = "l-load-copy" if self.copy else "l-load"
        return f"{op} {self.local_id}{depth}"


@attrs.frozen(eq=False)
class StoreXStack(StoreOp):
    depth: int = attrs.field(validator=attrs.validators.ge(0))
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_x_stack(self)

    def __str__(self) -> str:
        return f"x-store {self.local_id}"


@attrs.frozen(eq=False)
class LoadXStack(LoadOp):
    depth: int = attrs.field(validator=attrs.validators.ge(0))
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (self.local_id,)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_x_stack(self)

    def __str__(self) -> str:
        return f"x-load {self.local_id}"


@attrs.frozen(eq=False)
class StoreFStack(StoreOp):
    depth: int = attrs.field(validator=attrs.validators.ge(0))
    frame_index: int = attrs.field(validator=attrs.validators.ge(0))
    insert: bool = False
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_f_stack(self)

    def __str__(self) -> str:
        return f"f-store {self.local_id}"


@attrs.frozen(eq=False)
class LoadFStack(LoadOp):
    depth: int = attrs.field(validator=attrs.validators.ge(0))
    frame_index: int = attrs.field(validator=attrs.validators.ge(0))
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (f"{self.local_id} (copy)",)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_f_stack(self)

    def __str__(self) -> str:
        return f"f-load {self.local_id}"


@attrs.frozen(eq=False)
class LoadParam(LoadOp):
    index: int
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return (f"{self.local_id} (copy)",)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_load_param(self)

    def __str__(self) -> str:
        return f"p-load {self.local_id}"


@attrs.frozen(eq=False)
class StoreParam(StoreOp):
    index: int
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_store_param(self)

    def __str__(self) -> str:
        return f"p-store {self.local_id}"


@attrs.frozen(eq=False)
class Pop(MemoryOp):
    n: int
    consumes: int = attrs.field(init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_pop(self)

    def __str__(self) -> str:
        return f"pop {self.n}"


@attrs.frozen(eq=False)
class Proto(BaseOp):
    parameters: int
    returns: int
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_proto(self)

    def __str__(self) -> str:
        return f"proto {self.parameters} {self.returns}"


@attrs.frozen(eq=False)
class Allocate(BaseOp):
    bytes_vars: Sequence[str]
    uint64_vars: Sequence[str]
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

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
    consumes: int = attrs.field(init=False)
    produces: Sequence[str] = attrs.field()

    @consumes.default
    def _consumes(self) -> int:
        return self.parameters

    @produces.validator
    def _validate_produces(self, _: object, value: Sequence[str]) -> None:
        assert len(value) == self.returns, "invalid produces size"

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_callsub(self)

    def __str__(self) -> str:
        return f"callsub {self.target}"


@attrs.frozen(eq=False)
class RetSub(MemoryOp):
    returns: int
    fx_height: int = 0
    # l-stack is discarded after this op
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_retsub(self)

    def __str__(self) -> str:
        return "retsub"


@attrs.frozen(eq=False)
class IntrinsicOp(BaseOp):
    """An Op that does something other than just manipulating memory"""

    # TODO: use enum values for these ops
    op_code: str
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
        result = [self.op_code, *map(str, self.immediates)]
        if self.comment:
            result += ("//", self.comment)
        return " ".join(result)


class BranchingOp(IntrinsicOp, abc.ABC):
    @abc.abstractmethod
    def targets(self) -> Sequence[str]: ...


@attrs.frozen(eq=False)
class Branch(BranchingOp):
    op_code: str = attrs.field(default="b", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)
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
    produces: Sequence[str] = attrs.field(default=(), init=False)
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
    produces: Sequence[str] = attrs.field(default=(), init=False)
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
    produces: Sequence[str] = attrs.field(default=(), init=False)
    immediates: Sequence[str] = attrs.field(converter=tuple[str, ...])

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.frozen(eq=False)
class Match(BranchingOp):
    op_code: str = attrs.field(default="match", init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)
    immediates: Sequence[str] = attrs.field(converter=tuple[str, ...])
    consumes: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return len(self.immediates) + 1

    def targets(self) -> Sequence[str]:
        return self.immediates


@attrs.define(eq=False, repr=False)
class MemoryBasicBlock:
    block_name: str
    ops: list[BaseOp]
    predecessors: list[str]
    successors: list[str]
    source_location: SourceLocation
    # the ordering of values on the stack is used by debug maps
    # the assumption is lower levels won't change the order of variables in the stack
    # however they can introduce changes that do that ordering more efficiently
    x_stack_in: Sequence[str] | None = None
    """local_ids on x-stack on entry to a block"""
    x_stack_out: Sequence[str] | None = None
    """local_ids on x-stack on exit from a block"""
    f_stack_in: Sequence[str] = attrs.field(factory=list)
    """local_ids on f-stack on entry to a block"""
    f_stack_out: Sequence[str] = attrs.field(factory=list)
    """local_ids on f-stack on exit from a block"""

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

    id: str
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
    id: str
    main: MemorySubroutine
    subroutines: list[MemorySubroutine]
    avm_version: int

    @property
    def all_subroutines(self) -> Iterator[MemorySubroutine]:
        yield self.main
        yield from self.subroutines


def produces_from_desc(desc: str, size: int) -> Sequence[str]:
    desc = f"{{{desc}}}"
    if size > 1:
        produces = [f"{desc}.{n}" for n in range(size)]
    elif size == 1:
        produces = [desc]
    else:
        produces = []
    return produces
