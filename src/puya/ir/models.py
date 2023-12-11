import abc
import typing as t
from collections.abc import Iterable, Iterator, Sequence

import attrs

from puya.avm_type import AVMType
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.avm_ops_models import OpSignature
from puya.ir.types_ import AVMBytesEncoding, stack_type_to_avm_type
from puya.ir.visitor import IRVisitor
from puya.metadata import ContractMetaData
from puya.parse import SourceLocation

T = t.TypeVar("T")


class Context(t.Protocol):
    source_location: SourceLocation | None


class IRVisitable(Context, abc.ABC):
    @abc.abstractmethod
    def accept(self, visitor: IRVisitor[T]) -> T:
        ...

    def __str__(self) -> str:
        from puya.ir.to_text_visitor import ToTextVisitor

        return self.accept(ToTextVisitor())


# NOTE! we don't want structural equality in the IR, everything needs to have eq=False
#       the workaround to do this (trivial in Python to extend a decorator) AND have mypy
#       not complain is ... well, see for yourself:
#       https://www.attrs.org/en/stable/extending.html#wrapping-the-decorator
@attrs.define(eq=False)
class ValueProvider(IRVisitable, abc.ABC):
    """A node that provides/produces a value"""

    source_location: SourceLocation | None

    @property
    @abc.abstractmethod
    def types(self) -> Sequence[AVMType]:
        ...


@attrs.define(eq=False)
class Value(ValueProvider, abc.ABC):
    """Base class for value types.

    This is anything that *is* a value, so excludes
    value *producers* such as subroutine invocations
    """

    atype: AVMType

    @property
    def types(self) -> Sequence[AVMType]:
        return (self.atype,)


class Constant(Value, abc.ABC):
    """Base class for value constants - any value that is known at compile time"""


@attrs.define(eq=False)
class Op(IRVisitable, abc.ABC):
    """Base class for non-control-flow, non-phi operations

    This is anything other than a Phi can appear inside a BasicBlock before the terminal ControlOp.
    """


@attrs.define(eq=False)
class ControlOp(IRVisitable, abc.ABC):
    """Base class for control-flow operations

    These appear in a BasicBlock as the terminal node.
    """

    source_location: SourceLocation | None

    @abc.abstractmethod
    def targets(self) -> Sequence["BasicBlock"]:
        """For graph traversal - result could be empty if it's the end of the current graph"""


@attrs.frozen
class Register(Value):
    """A register is an abstraction of "local variable storage".

    This could be mapped to either value on the stack or a scratch slot during code generation.
    """

    name: str
    version: int
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_register(self)

    @property
    def local_id(self) -> str:
        return f"{self.name}#{self.version}"


@attrs.define(eq=False)
class PhiArgument(IRVisitable):
    value: Register
    through: "BasicBlock"
    source_location: None = attrs.field(default=None, init=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_phi_argument(self)


@attrs.define(eq=False)
class Phi(IRVisitable):
    """Phi nodes are oracles that, given a list of other variables, always produce the
    one that has been defined in the control flow thus far.

    The term phi node comes from the literature on Static Single Assignment
    """

    register: Register
    args: list[PhiArgument] = attrs.field(factory=list)
    source_location: None = attrs.field(default=None, init=False)
    undefined_predecessors: list["BasicBlock"] = attrs.field(factory=list)

    @property
    def atype(self) -> AVMType:
        return self.register.atype

    @property
    def non_self_args(self) -> Sequence[PhiArgument]:
        return tuple(a for a in self.args if a.value != self.register)

    @args.validator
    def check_args(self, _attribute: object, args: Sequence[PhiArgument]) -> None:
        bad_args = [arg for arg in args if not (arg.value.atype & self.atype)]
        if bad_args:
            raise InternalError(f"Phi node received arguments with unexpected type(s): {bad_args}")
        seen_blocks = set[BasicBlock]()
        for arg in args:
            if arg.through in seen_blocks:
                raise InternalError(f"Duplicate source to phi node: {arg.through}")
            seen_blocks.add(arg.through)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_phi(self)


@attrs.define(eq=False)
class UInt64Constant(Constant):
    value: int
    atype: AVMType = attrs.field(default=AVMType.uint64, init=False)
    teal_alias: str | None = attrs.field(default=None)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_uint64_constant(self)


@attrs.define(eq=False)
class BigUIntConstant(Constant):
    value: int
    atype: AVMType = attrs.field(default=AVMType.bytes, init=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_biguint_constant(self)


@attrs.define(eq=False)
class BytesConstant(Constant):
    """Constant for types that are logically bytes"""

    atype: AVMType = attrs.field(default=AVMType.bytes, init=False)

    encoding: AVMBytesEncoding

    value: bytes

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_bytes_constant(self)


@attrs.define(eq=False)
class AddressConstant(Constant):
    """Constant for address literals"""

    atype: AVMType = attrs.field(default=AVMType.bytes, init=False)

    value: str

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_address_constant(self)


@attrs.define(eq=False)
class MethodConstant(Constant):
    """Constant for method literals"""

    atype: AVMType = attrs.field(default=AVMType.bytes, init=False)

    value: str

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_method_constant(self)


@attrs.define(eq=False)
class Intrinsic(Op, ValueProvider):
    """Any TEAL op (or pseudo-op) that doesn't interrupt control flow, in the "basic block" sense.

    refs:
    - https://developer.algorand.org/docs/get-details/dapps/avm/teal/opcodes/
    - https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#assembler-syntax
    """

    op: AVMOp
    # TODO: validation for immediates && args
    # TODO: consider treating ops with no args (only immediates) as Value types
    #       e.g. `txn NumAppArgs` or `txna ApplicationArgs 0`
    immediates: list[str | int] = attrs.field(factory=list)
    args: list[Value] = attrs.field(factory=list)
    comment: str | None = None  # used e.g. for asserts

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_intrinsic_op(self)

    @property
    def types(self) -> Sequence[AVMType]:
        return tuple(map(stack_type_to_avm_type, self.op_signature.returns))

    @property
    def op_signature(self) -> OpSignature:
        return self.op.get_signature(self.immediates)


@attrs.define(eq=False)
class InvokeSubroutine(Op, ValueProvider):
    """Subroutine invocation

    opcode: callsub"""

    target: "Subroutine"
    # TODO: validation for args
    args: list[Value]

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_invoke_subroutine(self)

    @property
    def types(self) -> Sequence[AVMType]:
        return self.target.returns


@attrs.define(eq=False)
class ValueTuple(ValueProvider):
    values: list[Value]

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_value_tuple(self)

    @property
    def types(self) -> Sequence[AVMType]:
        return [val.atype for val in self.values]


@attrs.define(eq=False)
class Assignment(Op):
    """
    Assignment of either a value or the result of something that produces a value to register(s)
    """

    source_location: SourceLocation | None
    targets: list[Register] = attrs.field(validator=[attrs.validators.min_len(1)])
    source: ValueProvider = attrs.field()

    @source.validator
    def _check_types(self, _attribute: object, source: ValueProvider) -> None:
        target_type = [target.atype for target in self.targets]
        source_type = list(source.types)
        if not all(a & b for a, b in zip(target_type, source_type, strict=True)):
            raise CodeError(
                f"Incompatible types on assignment:"
                f" source = {source_type}, target = {target_type}",
                self.source_location,
            )

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_assignment(self)


@attrs.define(eq=False, str=False, kw_only=True)
class BasicBlock(Context):
    """IR basic block.

    Contains a sequence of operations and ends with a terminating ControlOp.
    Only the last op can be a ControlOp.

    All generated Ops live in basic blocks. Basic blocks determine the
    order of evaluation and control flow within a function. A basic
    block is always associated with a single Subroutine or program main.

    Ops that may terminate the program due to a panic or similar aren't treated as exits.
    """

    source_location: SourceLocation  # the location that caused the block to be constructed
    phis: list[Phi] = attrs.field(factory=list)
    ops: list[Op] = attrs.field(factory=list)
    terminator: ControlOp | None = attrs.field(default=None)
    predecessors: "list[BasicBlock]" = attrs.field(factory=list)
    id: int | None = None
    comment: str | None = None

    @phis.validator
    def _check_phis(self, _attribute: object, phis: list[Phi]) -> None:
        for phi in phis:
            attrs.validate(phi)

    @ops.validator
    def _check_ops(self, _attribute: object, ops: list[Op]) -> None:
        for op in ops:
            attrs.validate(op)

    @terminator.validator
    def _check_terminator(self, _attribute: object, terminator: ControlOp | None) -> None:
        if terminator is not None:
            attrs.validate(terminator)

    @property
    def terminated(self) -> bool:
        return self.terminator is not None

    @property
    def successors(self) -> "Sequence[BasicBlock]":
        if self.terminator is None:
            return ()
        return self.terminator.targets()

    @property
    def all_ops(self) -> Iterator[Phi | Op | ControlOp]:
        yield from self.phis.copy()
        yield from self.ops.copy()  # copy in case ops is modified
        if self.terminator is not None:
            yield self.terminator

    def get_assigned_registers(self) -> Iterator[Register]:
        for phi in self.phis:
            yield phi.register
        for op in self.ops:
            if isinstance(op, Assignment):
                yield from op.targets

    def __str__(self) -> str:
        result = f"block@{self.id}: // "
        if self.comment:
            result += f"{self.comment}_"
        result += f"L{self.source_location.line}"
        return result


@attrs.define(eq=False, kw_only=True)
class ConditionalBranch(ControlOp):
    """Branch based on zero-ness

    opcode: bz+b or bnz+b
    """

    condition: Value = attrs.field()
    non_zero: BasicBlock
    zero: BasicBlock

    @condition.validator
    def check(self, _attribute: object, result: Value) -> None:
        if result.atype != AVMType.uint64:
            raise CodeError(
                "Branch condition can only be uint64 typed value", self.source_location
            )

    def targets(self) -> Sequence[BasicBlock]:
        return self.zero, self.non_zero

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_conditional_branch(self)


@attrs.define(eq=False)
class Goto(ControlOp):
    """Unconditional jump

    opcode: b
    """

    target: BasicBlock

    def targets(self) -> Sequence[BasicBlock]:
        return (self.target,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_goto(self)


@attrs.define(eq=False)
class GotoNth(ControlOp):
    """Jump to the nth block in a list where n is defined by a UInt16 Value.
    Jumps to the default if n is larger than the number of blocks

    opcode: switch+b"""

    value: Value
    blocks: list[BasicBlock] = attrs.field()
    default: BasicBlock

    def targets(self) -> Sequence[BasicBlock]:
        return [*self.blocks, self.default]

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_goto_nth(self)


@attrs.define(eq=False)
class Switch(ControlOp):
    """Jump based on comparison between a value and a fixed list of other values.
    If no match is found, jumps to "default". This default option doesn't exist in
    the underlying op code, but we need it to make this truly terminate the basic block
    it's in, otherwise it'd violate certain CFG constraints.

    opcode: match+b
    """

    value: Value
    cases: dict[Value, BasicBlock] = attrs.field()
    default: BasicBlock

    @cases.validator
    def _check_cases(self, _attribute: object, cases: dict[Value, BasicBlock]) -> None:
        if any(case.atype != self.value.atype for case in cases):
            raise CodeError(
                "Switch cases types mismatch with value to match", self.source_location
            )

    def targets(self) -> Sequence[BasicBlock]:
        return [*self.cases.values(), self.default]

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_switch(self)


@attrs.define(eq=False)
class SubroutineReturn(ControlOp):
    """Return from within a subroutine

    opcode: retsub
    """

    result: list[Value]

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_subroutine_return(self)


@attrs.define(eq=False)
class ProgramExit(ControlOp):
    """Return from and exit the program immediately

    opcode: return
    """

    result: Value = attrs.field()

    @result.validator
    def check(self, _attribute: object, result: Value) -> None:
        if result.atype != AVMType.uint64:
            raise CodeError("Can only exit with uint64 typed value", self.source_location)

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_program_exit(self)


@attrs.define(eq=False)
class Fail(ControlOp):
    """Exits immediately with a failure condition.

    assert statements with a compile time constant that is false
    should be translated to this node type in order to become ControlOp


    opcode: err
    """

    comment: str | None

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_fail(self)


@attrs.define(eq=False)
class Subroutine(Context):
    # source_location might be None if it was synthesized e.g. ARC4 approval method
    source_location: SourceLocation | None
    module_name: str
    class_name: str | None  # None if a function (vs a method)
    method_name: str
    parameters: Sequence[Register]
    returns: Sequence[AVMType]
    body: list[BasicBlock] = attrs.field()

    @body.validator
    def _check_blocks(self, _attribute: object, body: list[BasicBlock]) -> None:
        blocks = frozenset(body)
        for block in body:
            attrs.validate(block)
            if block.terminator is None:
                raise InternalError(
                    f"Unterminated block {block.id} assigned to subroutine {self.full_name}",
                    block.source_location,
                )
            for successor in block.successors:
                if block not in successor.predecessors:
                    # Note: this check is here rather than on BasicBlock only because of
                    # circular validation issues where you're trying to update the CFG by
                    # replacing a terminator
                    raise InternalError(
                        f"Block {block.id} does not appear in all {block.terminator}"
                        f" target's predecessor lists - missing from {successor.id} at least",
                        block.terminator.source_location
                        or block.source_location
                        or self.source_location,
                    )
            if not blocks.issuperset(block.predecessors):
                raise InternalError(
                    f"Block {block.id} of subroutine {self.full_name}"
                    " has predecessor block(s) outside of list",
                    block.source_location,
                )
            if not blocks.issuperset(block.successors):
                raise InternalError(
                    f"Block {block.id} of subroutine {self.full_name}"
                    " has predecessor block(s) outside of list",
                    block.source_location,
                )
            block_predecessors = dict.fromkeys(block.predecessors)
            for phi in block.phis:
                phi_blocks = dict.fromkeys(a.through for a in phi.args) | dict.fromkeys(
                    phi.undefined_predecessors
                )
                if block_predecessors.keys() != phi_blocks.keys():
                    phi_block_labels = list(map(str, phi_blocks.keys()))
                    pred_block_labels = list(map(str, block_predecessors.keys()))
                    raise InternalError(
                        f"Mismatch between phi predecessors ({phi_block_labels})"
                        f" and block predecessors ({pred_block_labels})"
                        f" for phi node {phi}",
                        self.source_location,
                    )
        used_registers = frozenset(self.get_used_registers())
        defined_registers = frozenset(self.get_assigned_registers())
        bad_reads = used_registers - defined_registers
        if bad_reads:
            raise InternalError(
                f"The following variables are used but never defined:"
                f" {', '.join(map(str, bad_reads))}",
                self.source_location,
            )

    @property
    def full_name(self) -> str:
        return ".".join(filter(None, (self.module_name, self.class_name, self.method_name)))

    @property
    def entry(self) -> BasicBlock:
        return self.body[0]

    def get_assigned_registers(self) -> Iterator[Register]:
        yield from self.parameters
        # TODO: replace with visitor
        for block in self.body:
            for phi in block.phis:
                yield phi.register
            for op in block.ops:
                if isinstance(op, Assignment):
                    yield from op.targets

    def get_used_registers(self) -> Iterator[Register]:
        # TODO: replace with visitor
        for block in self.body:
            for phi in block.phis:
                yield from (arg.value for arg in phi.args)
            for op in block.ops:
                match op:
                    case (
                        Assignment(
                            source=Intrinsic(args=args)
                            | Assignment(source=ValueTuple(values=args))
                            | InvokeSubroutine(args=args)
                        )
                        | Intrinsic(args=args)
                        | InvokeSubroutine(args=args)
                    ):
                        yield from (arg for arg in args if isinstance(arg, Register))
                    case Assignment(source=Register() as reg):
                        yield reg

    def validate_with_ssa(self) -> None:
        all_assigned = set[Register]()
        for block in self.body:
            for register in block.get_assigned_registers():
                if register in all_assigned:
                    raise InternalError(
                        f"SSA constraint violated:"
                        f" {register.local_id} is assigned multiple times"
                    )
                all_assigned.add(register)
        attrs.validate(self)


@attrs.define(eq=False)
class Program(Context):
    """An individual compilation unit - ie either an Approval or a Clear State program"""

    # note: main is represented as a subroutine for simplified handling,
    # but should be "inlined" as main contract body during codegen.
    # ie, it could be generated as subroutine "main" with proto 0 1,
    # and then start of contract becomes:
    #
    # callsub main
    # return
    # main:
    #   proto 0 1
    #   ...
    #   retsub
    #
    # but, to save program size + op codes, this should be simplified to:
    # ...
    # return
    #
    # ie, just omit the subroutine header, and replace any&all retsub ops with a return instead
    main: Subroutine
    subroutines: Sequence[Subroutine]
    source_location: SourceLocation | None = None

    def __attrs_post_init__(self) -> None:
        if self.source_location is None:
            self.source_location = self.main.source_location

    @property
    def all_subroutines(self) -> Iterable[Subroutine]:
        yield self.main
        yield from self.subroutines


@attrs.define(eq=False)
class Contract(Context):
    source_location: SourceLocation
    approval_program: Program
    clear_program: Program
    metadata: ContractMetaData

    def all_subroutines(self) -> Iterable[Subroutine]:
        from itertools import chain

        from puya.utils import unique

        yield from unique(
            chain(
                self.approval_program.all_subroutines,
                self.clear_program.all_subroutines,
            )
        )
