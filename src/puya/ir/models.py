import abc
import typing
import typing as t
from collections.abc import Iterable, Iterator, Sequence

import attrs

from puya import log
from puya.avm_type import AVMType
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.avm_ops_models import OpSignature, StackType, Variant
from puya.ir.types_ import AVMBytesEncoding, IRType, stack_type_to_avm_type, stack_type_to_ir_type
from puya.ir.visitor import IRVisitor
from puya.models import ContractMetaData, LogicSignatureMetaData
from puya.parse import SourceLocation
from puya.utils import unique

logger = log.get_logger(__name__)

T = t.TypeVar("T")


class Context(t.Protocol):
    source_location: SourceLocation | None


class IRVisitable(Context, abc.ABC):
    @abc.abstractmethod
    def accept(self, visitor: IRVisitor[T]) -> T: ...

    def __str__(self) -> str:
        from puya.ir.to_text_visitor import ToTextVisitor

        return self.accept(ToTextVisitor())


class _Freezable(abc.ABC):
    def freeze(self) -> object:
        data = self._frozen_data()
        hash(data)  # check we can hash
        if data is self:
            return data
        return self.__class__, data

    @abc.abstractmethod
    def _frozen_data(self) -> object: ...


# NOTE! we don't want structural equality in the IR, everything needs to have eq=False
#       the workaround to do this (trivial in Python to extend a decorator) AND have mypy
#       not complain is ... well, see for yourself:
#       https://www.attrs.org/en/stable/extending.html#wrapping-the-decorator
@attrs.define(eq=False)
class ValueProvider(IRVisitable, _Freezable, abc.ABC):
    """A node that provides/produces a value"""

    source_location: SourceLocation | None = attrs.field(eq=False)

    @property
    @abc.abstractmethod
    def types(self) -> Sequence[IRType]: ...

    @property
    @t.final
    def atypes(self) -> Sequence[AVMType]:
        return tuple(t.avm_type for t in self.types)


@attrs.frozen
class Value(ValueProvider, abc.ABC):
    """Base class for value types.

    This is anything that *is* a value, so excludes
    value *producers* such as subroutine invocations
    """

    ir_type: IRType = attrs.field(repr=lambda x: x.name)

    @property
    @t.final
    def atype(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        return self.ir_type.avm_type

    @property
    def types(self) -> Sequence[IRType]:
        return (self.ir_type,)

    def _frozen_data(self) -> object:
        return self


class Constant(Value, abc.ABC):
    """Base class for value constants - any value that is known at compile time"""


@attrs.define(eq=False)
class Op(IRVisitable, _Freezable, abc.ABC):
    """Base class for non-control-flow, non-phi operations

    This is anything other than a Phi can appear inside a BasicBlock before the terminal ControlOp.
    """


@attrs.define(eq=False)
class ControlOp(IRVisitable, _Freezable, abc.ABC):
    """Base class for control-flow operations

    These appear in a BasicBlock as the terminal node.
    """

    source_location: SourceLocation | None

    @abc.abstractmethod
    def targets(self) -> Sequence["BasicBlock"]:
        """For graph traversal - result could be empty if it's the end of the current graph"""

    @property
    def unique_targets(self) -> list["BasicBlock"]:
        return unique(self.targets())

    @property
    @abc.abstractmethod
    def can_exit(self) -> bool:
        """Does this ControlOp exit the current subroutine (somehow - eg terminates, returns)"""


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
class Phi(IRVisitable, _Freezable):
    """Phi nodes are oracles that, given a list of other variables, always produce the
    one that has been defined in the control flow thus far.

    The term phi node comes from the literature on Static Single Assignment
    """

    register: Register
    args: list[PhiArgument] = attrs.field(factory=list)
    source_location: None = attrs.field(default=None, init=False)
    undefined_predecessors: list["BasicBlock"] = attrs.field(factory=list)

    @property
    def ir_type(self) -> IRType:
        return self.register.ir_type

    @property
    def atype(self) -> AVMType:
        return self.ir_type.avm_type

    @property
    def non_self_args(self) -> Sequence[PhiArgument]:
        return tuple(a for a in self.args if a.value != self.register)

    def _frozen_data(self) -> object:
        return (
            self.register.freeze(),
            tuple((arg.through.id, arg.value.freeze()) for arg in self.args),
            (b.id for b in self.undefined_predecessors),
        )

    @args.validator
    def check_args(self, _attribute: object, args: Sequence[PhiArgument]) -> None:
        bad_args = [
            arg for arg in args if arg.value.ir_type.maybe_avm_type != self.ir_type.maybe_avm_type
        ]
        if bad_args:
            raise InternalError(
                f"Phi node (register={self.register}) received arguments with unexpected type(s):"
                f" {', '.join(map(str, bad_args))}, "
            )
        seen_blocks = set[BasicBlock]()
        for arg in args:
            if arg.through in seen_blocks:
                raise InternalError(f"Duplicate source to phi node: {arg.through}")
            seen_blocks.add(arg.through)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_phi(self)


@attrs.frozen(kw_only=True)
class UInt64Constant(Constant):
    value: int
    ir_type: IRType = attrs.field(default=IRType.uint64)
    teal_alias: str | None = None
    source_location: SourceLocation | None = attrs.field(eq=False)

    @ir_type.validator
    def _validate_ir_type(self, _attribute: object, ir_type: IRType) -> None:
        if ir_type.avm_type is not AVMType.uint64:
            raise InternalError(
                f"Invalid type for UInt64Constant: {ir_type}", self.source_location
            )

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_uint64_constant(self)


@attrs.frozen(kw_only=True)
class ITxnConstant(Constant):
    value: int
    ir_type: IRType = attrs.field()
    source_location: SourceLocation | None = attrs.field(eq=False)

    @ir_type.validator
    def _validate_ir_type(self, _attribute: object, ir_type: IRType) -> None:
        if ir_type not in (IRType.itxn_group_idx, IRType.itxn_field_set):
            raise InternalError(f"Invalid type for ITxnConstant: {ir_type}", self.source_location)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_itxn_constant(self)


@attrs.frozen
class BigUIntConstant(Constant):
    value: int
    ir_type: IRType = attrs.field(default=IRType.biguint, init=False)
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_biguint_constant(self)


@attrs.frozen
class TemplateVar(Value):
    name: str
    ir_type: IRType

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_template_var(self)


@attrs.frozen
class BytesConstant(Constant):
    """Constant for types that are logically bytes"""

    ir_type: IRType = attrs.field(default=IRType.bytes, init=False)

    encoding: AVMBytesEncoding
    value: bytes
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_bytes_constant(self)


@attrs.frozen
class AddressConstant(Constant):
    """Constant for address literals"""

    ir_type: IRType = attrs.field(default=IRType.bytes, init=False)
    value: str
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_address_constant(self)


@attrs.frozen
class MethodConstant(Constant):
    """Constant for method literals"""

    ir_type: IRType = attrs.field(default=IRType.bytes, init=False)
    value: str
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_method_constant(self)


@attrs.define(eq=False)
class InnerTransactionField(Op, ValueProvider):
    field: str
    group_index: Value
    is_last_in_group: Value
    array_index: Value | None
    type: IRType

    def _frozen_data(self) -> object:
        return self.field, self.group_index, self.is_last_in_group, self.array_index, self.type

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_inner_transaction_field(self)

    @property
    def types(self) -> Sequence[IRType]:
        return (self.type,)


@attrs.define(eq=False)
class Intrinsic(Op, ValueProvider):
    """Any TEAL op (or pseudo-op) that doesn't interrupt control flow, in the "basic block" sense.

    refs:
    - https://developer.algorand.org/docs/get-details/dapps/avm/teal/opcodes/
    - https://developer.algorand.org/docs/get-details/dapps/avm/teal/specification/#assembler-syntax
    """

    op: AVMOp
    # TODO: consider treating ops with no args (only immediates) as Value types
    #       e.g. `txn NumAppArgs` or `txna ApplicationArgs 0`
    immediates: list[str | int] = attrs.field(factory=list)
    args: list[Value] = attrs.field(factory=list)
    comment: str | None = None  # used e.g. for asserts
    _types: Sequence[IRType] = attrs.field(converter=tuple[IRType, ...])

    @_types.default
    def _default_types(self) -> tuple[IRType, ...]:
        types = list[IRType]()
        for stack_type in self.op_signature.returns:
            ir_type = stack_type_to_ir_type(stack_type)
            if ir_type is None:
                raise InternalError(
                    f"Intrinsic op {self.op.name} requires return type information",
                    self.source_location,
                )
            types.append(ir_type)
        return tuple(types)

    def _frozen_data(self) -> object:
        return self.op, tuple(self.immediates), tuple(self.args), self.comment

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_intrinsic_op(self)

    @property
    def types(self) -> Sequence[IRType]:
        return self._types

    @property
    def op_signature(self) -> OpSignature:
        return self.op_variant.signature

    @property
    def op_variant(self) -> Variant:
        return self.op.get_variant(self.immediates)

    @_types.validator
    def _validate_types(self, _attribute: object, types: Sequence[IRType]) -> None:
        self._check_stack_types("return", self.op_signature.returns, types)

    @args.validator
    def _validate_args(self, _attribute: object, args: list[Value]) -> None:
        arg_types = [a.ir_type for a in args]
        self._check_stack_types("argument", self.op_signature.args, arg_types)

    def _check_stack_types(
        self,
        context: str,
        expected_types: Sequence[StackType],
        source_types: Sequence[IRType],
    ) -> None:
        target_types = [stack_type_to_avm_type(a) for a in expected_types]
        if len(target_types) != len(source_types) or not all(
            tt & st.avm_type for tt, st in zip(target_types, source_types, strict=True)
        ):
            logger.error(
                (
                    f"Incompatible {context} types on Intrinsic"
                    f"({self.op} {' '.join(map(str, self.immediates))}): "
                    f" received = ({', '.join(map(str, source_types))}),"
                    f" expected = ({', '.join(map(str, target_types))})"
                ),
                location=self.source_location,
            )


@attrs.define(eq=False)
class InvokeSubroutine(Op, ValueProvider):
    """Subroutine invocation

    opcode: callsub"""

    target: "Subroutine"
    # TODO: validation for args
    args: list[Value]

    def _frozen_data(self) -> object:
        return self.target.full_name, tuple(self.args)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_invoke_subroutine(self)

    @property
    def types(self) -> Sequence[IRType]:
        return self.target.returns


@attrs.define(eq=False)
class ValueTuple(ValueProvider):
    values: list[Value]

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_value_tuple(self)

    @property
    def types(self) -> Sequence[IRType]:
        return [val.ir_type for val in self.values]

    def _frozen_data(self) -> object:
        return tuple(self.values)


@attrs.define(eq=False)
class Assignment(Op):
    """
    Assignment of either a value or the result of something that produces a value to register(s)
    """

    source_location: SourceLocation | None
    targets: list[Register] = attrs.field(validator=[attrs.validators.min_len(1)])
    source: ValueProvider = attrs.field()

    def _frozen_data(self) -> object:
        return tuple(self.targets), self.source.freeze()

    @source.validator
    def _check_types(self, _attribute: object, source: ValueProvider) -> None:
        target_ir_types = [target.ir_type for target in self.targets]
        source_ir_types = list(source.types)
        if target_ir_types != source_ir_types:
            # TODO: need to update some optimiser code and/or
            #       introduce ReinterpretCast ValueProvider
            #       here before we can remove this fallback to AVMType here
            target_atypes = [tt.maybe_avm_type for tt in target_ir_types]
            source_atypes = [st.maybe_avm_type for st in source_ir_types]
            if target_atypes != source_atypes:
                raise CodeError(
                    f"Incompatible types on assignment:"
                    f" source = ({', '.join(map(str, source_ir_types))}),"
                    f" target = ({', '.join(map(str, target_ir_types))})",
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

    def _frozen_data(self) -> object:
        return self.condition.freeze(), self.non_zero.id, self.zero.id

    @condition.validator
    def check(self, _attribute: object, result: Value) -> None:
        if result.atype != AVMType.uint64:
            raise CodeError(
                "Branch condition can only be uint64 backed value", self.source_location
            )

    def targets(self) -> Sequence[BasicBlock]:
        return self.zero, self.non_zero

    @property
    def can_exit(self) -> bool:
        return False

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_conditional_branch(self)


@attrs.define(eq=False)
class Goto(ControlOp):
    """Unconditional jump

    opcode: b
    """

    target: BasicBlock

    def _frozen_data(self) -> object:
        return self.target.id

    def targets(self) -> Sequence[BasicBlock]:
        return (self.target,)

    @property
    def can_exit(self) -> bool:
        return False

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_goto(self)


@attrs.define(eq=False)
class GotoNth(ControlOp):
    """Jump to the nth block in a list where n is defined by a UInt16 Value.
    Jumps to the default if n is larger than the number of blocks

    opcode: switch+b"""

    value: Value
    blocks: list[BasicBlock] = attrs.field()
    default: ControlOp

    def _frozen_data(self) -> object:
        return self.value, tuple(b.id for b in self.blocks), self.default.freeze()

    def targets(self) -> Sequence[BasicBlock]:
        return [*self.blocks, *self.default.targets()]

    @property
    def can_exit(self) -> bool:
        return self.default.can_exit

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
    default: ControlOp

    @cases.validator
    def _check_cases(self, _attribute: object, cases: dict[Value, BasicBlock]) -> None:
        if any(case.atype != self.value.atype for case in cases):
            raise CodeError(
                "Switch cases types mismatch with value to match", self.source_location
            )

    def _frozen_data(self) -> object:
        return (
            self.value,
            tuple((v, b.id) for v, b in self.cases.items()),
            self.default.freeze(),
        )

    def targets(self) -> Sequence[BasicBlock]:
        return [*self.cases.values(), *self.default.targets()]

    @property
    def can_exit(self) -> bool:
        return self.default.can_exit

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_switch(self)


@attrs.define(eq=False)
class SubroutineReturn(ControlOp):
    """Return from within a subroutine

    opcode: retsub
    """

    result: list[Value]

    def _frozen_data(self) -> object:
        return tuple(self.result)

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    @property
    def can_exit(self) -> bool:
        return True

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
            raise CodeError("Can only exit with uint64 backed value", self.source_location)

    def _frozen_data(self) -> object:
        return self.result

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    @property
    def can_exit(self) -> bool:
        return True

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

    @property
    def can_exit(self) -> bool:
        return True

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_fail(self)

    def _frozen_data(self) -> object:
        return self.comment


@attrs.frozen
class Parameter(Register):
    implicit_return: bool


@attrs.define(eq=False)
class Subroutine(Context):
    # source_location might be None if it was synthesized e.g. ARC4 approval method
    source_location: SourceLocation | None
    module_name: str
    class_name: str | None  # None if a function (vs a method)
    method_name: str
    parameters: Sequence[Parameter]
    _returns: Sequence[IRType]
    body: list[BasicBlock] = attrs.field()

    @property
    def returns(self) -> list[IRType]:
        return [*self._returns, *(p.ir_type for p in self.parameters if p.implicit_return)]

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

    def all_programs(self) -> Iterable[Program]:
        return [self.approval_program, self.clear_program]


@attrs.define(eq=False)
class LogicSignature(Context):
    source_location: SourceLocation
    program: Program
    metadata: LogicSignatureMetaData

    def all_subroutines(self) -> Iterable[Subroutine]:
        return self.program.all_subroutines

    def all_programs(self) -> Iterable[Program]:
        return [self.program]


ModuleArtifact: t.TypeAlias = Contract | LogicSignature
