from __future__ import annotations

import abc
import typing
import typing as t

import attrs

from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir.utils import format_bytes, format_error_comment
from puya.program_refs import ProgramKind

if t.TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from puya.ir.types_ import AVMBytesEncoding
    from puya.mir.visitor import MIRVisitor
    from puya.parse import SourceLocation

_T = t.TypeVar("_T")


@attrs.frozen(kw_only=True, eq=False, str=False)
class BaseOp(abc.ABC):
    error_message: str | None = None
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
class Op(BaseOp, abc.ABC):
    @abc.abstractmethod
    def __str__(self) -> str: ...


@attrs.frozen(eq=False)
class Int(Op):
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
class Byte(Op):
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
class Undefined(Op):
    atype: typing.Literal[AVMType.bytes, AVMType.uint64]
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(validator=_is_single_item)

    @produces.default
    def _produces(self) -> Sequence[str]:
        return ("undefined",)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_undefined(self)

    def __str__(self) -> str:
        return "undefined"


@attrs.frozen(eq=False)
class TemplateVar(Op):
    name: str
    atype: AVMType
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
class Address(Op):
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
class Method(Op):
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
class Comment(Op):
    comment: str
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_comment(self)

    def __str__(self) -> str:
        return f"// {self.comment}"


@attrs.frozen(kw_only=True, eq=False)
class StoreOp(Op, abc.ABC):
    """An op for storing values"""

    local_id: str
    atype: AVMType = attrs.field()

    @atype.validator
    def _validate_not_any(self, _attribute: object, atype: AVMType) -> None:
        if atype is AVMType.any:
            raise InternalError(f"Register has type any: {self}", self.source_location)


@attrs.frozen(kw_only=True, eq=False)
class LoadOp(Op, abc.ABC):
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
class Pop(Op):
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
class CallSub(Op):
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
class IntrinsicOp(Op):
    """An Op that does something other than just manipulating memory"""

    # TODO: use enum values for these ops
    op_code: str
    immediates: Sequence[str | int] = attrs.field(default=(), converter=tuple[str | int, ...])

    def __attrs_post_init__(self) -> None:
        if self.op_code in ("b", "bz", "bnz", "switch", "match", "retsub", "err", "return"):
            raise InternalError(
                f"Branching op {self.op_code} should map to explicit MIR ControlOp",
                self.source_location,
            )

    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_intrinsic(self)

    def __str__(self) -> str:
        result = [self.op_code, *map(str, self.immediates)]
        if self.error_message:
            result.append("//")
            result.append(format_error_comment(self.op_code, self.error_message))
        return " ".join(result)


@attrs.frozen(eq=False)
class ControlOp(BaseOp, abc.ABC):
    @abc.abstractmethod
    def targets(self) -> Sequence[str]: ...

    @abc.abstractmethod
    def _str_components(self) -> tuple[str, ...]: ...

    @typing.final
    def __str__(self) -> str:
        result = tuple(self._str_components())
        if self.error_message:
            result += ("//", self.error_message)
        return " ".join(result)


@attrs.frozen(eq=False)
class RetSub(ControlOp):
    returns: int
    fx_height: int = 0
    # l-stack is discarded after this op
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_retsub(self)

    @typing.override
    def targets(self) -> Sequence[str]:
        return ()

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return ("retsub",)


@attrs.frozen(eq=False)
class ProgramExit(ControlOp):
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_program_exit(self)

    @typing.override
    def targets(self) -> Sequence[str]:
        return ()

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return ("return",)


@attrs.frozen(eq=False)
class Err(ControlOp):
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_err(self)

    @typing.override
    def targets(self) -> Sequence[str]:
        return ()

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return ("err",)


@attrs.frozen(eq=False)
class Goto(ControlOp):
    consumes: int = attrs.field(default=0, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)
    target: str

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_goto(self)

    @typing.override
    def targets(self) -> Sequence[str]:
        return (self.target,)

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return "b", self.target


@attrs.frozen(eq=False)
class ConditionalBranch(ControlOp):
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)
    zero_target: str
    nonzero_target: str

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_conditional_branch(self)

    @typing.override
    def targets(self) -> Sequence[str]:
        return self.zero_target, self.nonzero_target

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return "bz", self.zero_target, ";", "b", self.nonzero_target


@attrs.frozen(eq=False)
class Switch(ControlOp):
    consumes: int = attrs.field(default=1, init=False)
    produces: Sequence[str] = attrs.field(default=(), init=False)
    switch_targets: Sequence[str] = attrs.field(converter=tuple[str, ...])
    default_target: str

    @typing.override
    def targets(self) -> Sequence[str]:
        return *self.switch_targets, self.default_target

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_switch(self)

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return "switch", *self.switch_targets, ";", "b", self.default_target


@attrs.frozen(eq=False)
class Match(ControlOp):
    produces: Sequence[str] = attrs.field(default=(), init=False)
    match_targets: Sequence[str] = attrs.field(converter=tuple[str, ...])
    consumes: int = attrs.field(init=False)
    default_target: str

    @consumes.default
    def _consumes(self) -> int:
        return len(self.match_targets) + 1

    @typing.override
    def targets(self) -> Sequence[str]:
        return *self.match_targets, self.default_target

    @typing.override
    def accept(self, visitor: MIRVisitor[_T]) -> _T:
        return visitor.visit_match(self)

    @typing.override
    def _str_components(self) -> tuple[str, ...]:
        return "match", *self.match_targets, ";", "b", self.default_target


@attrs.define(eq=False, repr=False, kw_only=True)
class MemoryBasicBlock:
    id: int
    """Unique id within a subroutine"""
    block_name: str
    mem_ops: list[Op]
    terminator: ControlOp
    predecessors: list[str]
    source_location: SourceLocation | None
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

    @property
    def ops(self) -> Sequence[BaseOp]:
        return *self.mem_ops, self.terminator

    def __repr__(self) -> str:
        return self.block_name

    @property
    def entry_stack_height(self) -> int:
        return len(self.f_stack_in) + len(self.x_stack_in or ())

    @property
    def exit_stack_height(self) -> int:
        return len(self.f_stack_out) + len(self.x_stack_out or ())

    @property
    def successors(self) -> Sequence[str]:
        return self.terminator.targets()


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


@attrs.frozen(eq=False, kw_only=True)
class FStackPreAllocation:
    bytes_vars: Sequence[str]
    uint64_vars: Sequence[str]

    @classmethod
    def empty(cls) -> typing.Self:
        return cls(bytes_vars=(), uint64_vars=())

    @property
    def allocate_on_entry(self) -> Sequence[str]:
        return [*self.bytes_vars, *self.uint64_vars]

    def __bool__(self) -> bool:
        return bool(self.bytes_vars or self.uint64_vars)


@attrs.define
class MemorySubroutine:
    """A lower form of IR that is concerned with memory assignment (both stack and scratch)"""

    id: str
    is_main: bool
    signature: Signature
    body: Sequence[MemoryBasicBlock]
    pre_alloc: FStackPreAllocation | None
    source_location: SourceLocation | None


@attrs.frozen(kw_only=True)
class SlotAllocation:
    allocation_slot: int
    allocation_map: bytes


@attrs.define
class Program:
    kind: ProgramKind
    main: MemorySubroutine
    subroutines: list[MemorySubroutine]
    avm_version: int
    slot_allocation: SlotAllocation | None

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
