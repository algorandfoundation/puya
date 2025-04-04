import abc
import enum
import typing
import typing as t
from collections.abc import Iterable, Iterator, Mapping, Sequence, Set

import attrs
from immutabledict import immutabledict

from puya import log
from puya.artifact_metadata import ContractMetaData, LogicSignatureMetaData
from puya.avm import AVMType
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.avm_ops_models import ImmediateKind, OpSignature, Variant
from puya.ir.types_ import (
    ArrayType,
    AVMBytesEncoding,
    EncodedTupleType,
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    SlotType,
    UnionType,
    encoded_ir_type_to_ir_types,
)
from puya.ir.visitor import IRVisitor
from puya.parse import SourceLocation
from puya.program_refs import (
    ContractReference,
    LogicSigReference,
    ProgramKind,
)
from puya.utils import unique

logger = log.get_logger(__name__)

TMP_VAR_INDICATOR = "%"
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


@attrs.define
class Value(ValueProvider, abc.ABC):
    """Base class for value types.

    This is anything that *is* a value, so excludes
    value *producers* such as subroutine invocations
    """

    ir_type: IRType = attrs.field(repr=lambda x: x.name)

    @property
    @t.final
    def atype(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        atype = self.ir_type.avm_type
        if atype == AVMType.any:
            raise InternalError("unexpected any type", self.source_location)
        return atype

    @property
    def types(self) -> Sequence[IRType]:
        return (self.ir_type,)

    def _frozen_data(self) -> object:
        return self


def _is_uint64_type(_op: Context, _attribute: object, value: Value) -> None:
    if value.ir_type != PrimitiveIRType.uint64:
        raise InternalError(
            f"expected uint64 type, received: {value.ir_type}", value.source_location
        )


def _is_slot_type(_op: Context, _attribute: object, value: Value) -> None:
    (typ,) = value.types
    if not isinstance(typ, SlotType):
        raise InternalError(f"expected SlotType, received: {typ}", value.source_location)


def _narrow_to_slot_type(typ: IRType) -> SlotType:
    if not isinstance(typ, SlotType):
        raise InternalError(f"expected SlotType, received: {typ}")
    return typ


@attrs.frozen
class Undefined(Value):
    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_undefined(self)


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


@attrs.frozen
class Register(Value):
    """A register is an abstraction of "local variable storage".

    This could be mapped to either value on the stack or a scratch slot during code generation.
    """

    name: str
    version: int

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
    # uses a factory here so attrs.NOTHING can be used to signal default values
    ir_type: IRType = attrs.field(factory=lambda: PrimitiveIRType.uint64)
    teal_alias: str | None = None

    @ir_type.validator
    def _validate_ir_type(self, _attribute: object, ir_type: IRType) -> None:
        if ir_type.maybe_avm_type is not AVMType.uint64:
            raise InternalError(
                f"Invalid type for UInt64Constant: {ir_type}", self.source_location
            )

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_uint64_constant(self)


@attrs.frozen(kw_only=True)
class ITxnConstant(Constant):
    """
    Represents a static value relating to inner transactions, used to ensure static parameters
    such as gitxn group indexes are resolved to immediates, as there are no stack variant ops.

    During optimization will be moved into immediate fields as appropriate, if optimizations
    fail to do this, then this will result in a code error during the MIR lowering.

    TODO: maybe this could just be a UInt64Constant of the appropriate IRType?
    """

    value: int
    ir_type: IRType = attrs.field()

    @ir_type.validator
    def _validate_ir_type(self, _attribute: object, ir_type: IRType) -> None:
        if ir_type not in (
            PrimitiveIRType.itxn_group_idx,
            PrimitiveIRType.itxn_field_set,
        ):
            raise InternalError(f"invalid type for ITxnConstant: {ir_type}", self.source_location)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_itxn_constant(self)


@attrs.frozen(kw_only=True)
class SlotConstant(Constant):
    """
    Represents a local (local to a function) and static (i.e. compile time constant) "slot"
    Introduced only if a NewSlot op is determined to be static and local to a function, in which
    case it is replaced with this node so that during MIR the value can instead be allocated on
    the frame stack

    TODO: maybe this could just be a UInt64Constant of the appropriate IRType?
    """

    value: int
    """Used to determine a unique slot in a functions f-stack for this variable"""
    ir_type: SlotType = attrs.field(converter=_narrow_to_slot_type)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_slot_constant(self)


@attrs.frozen
class BigUIntConstant(Constant):
    value: int
    ir_type: IRType = attrs.field(default=PrimitiveIRType.biguint, init=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_biguint_constant(self)


@attrs.frozen
class TemplateVar(Value):
    name: str
    ir_type: IRType

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_template_var(self)


@attrs.frozen(kw_only=True)
class BytesConstant(Constant):
    """Constant for types that are logically bytes"""

    value: bytes
    encoding: AVMBytesEncoding
    ir_type: IRType = attrs.field()

    @ir_type.default
    def _ir_type(self) -> IRType:
        return SizedBytesType(num_bytes=len(self.value))

    @ir_type.validator
    def _validate_ir_type(self, _attribute: object, ir_type: IRType) -> None:
        if ir_type.maybe_avm_type is not AVMType.bytes:
            raise InternalError(f"invalid type for BytesConstant: {ir_type}", self.source_location)
        if isinstance(ir_type, SizedBytesType) and ir_type.num_bytes != len(self.value):
            raise InternalError(
                f"incorrect sized type for BytesConstant: {ir_type} + {self.value=}",
                self.source_location,
            )

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_bytes_constant(self)


@attrs.define
class CompiledContractReference(Value):
    """
    Represents static information about a contract after it is fully compiled,
    Used when creating or updating contracts using inner transactions
    """

    artifact: ContractReference
    """Reference to the contract being compiled"""
    field: TxnField
    template_variables: Mapping[str, Value] = attrs.field(converter=immutabledict)
    """
    template variable keys here are fully qualified with their appropriate prefix,
    """
    source_location: SourceLocation | None = attrs.field(eq=False)
    program_page: int | None = None  # used for approval and clear_state fields

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_compiled_contract_reference(self)


@attrs.define
class CompiledLogicSigReference(Value):
    artifact: LogicSigReference
    template_variables: Mapping[str, Value] = attrs.field(converter=immutabledict)
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_compiled_logicsig_reference(self)


@attrs.frozen
class AddressConstant(Constant):
    """Constant for address literals"""

    ir_type: IRType = attrs.field(default=SizedBytesType(32), init=False)
    value: str = attrs.field()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_address_constant(self)


@attrs.frozen
class MethodConstant(Constant):
    """Constant for method literals"""

    ir_type: IRType = attrs.field(default=SizedBytesType(4), init=False)
    value: str

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_method_constant(self)


@attrs.define(eq=False)
class InnerTransactionField(ValueProvider):
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


class ArrayOp(typing.Protocol):
    @property
    def array(self) -> Value: ...


def _value_has_encoded_array_element_type(
    op: ArrayOp, _attribute: object, value: "Value | ValueTuple"
) -> None:
    array_ir_type = _array_type(op.array)
    element_type = array_ir_type.element
    # this is only comparing the linear sequence of types,
    # as ValueTuple's do not retain the higher level structure
    element_types = encoded_ir_type_to_ir_types(element_type)
    values = (value,) if isinstance(value, Value) else value.values
    value_types = tuple(v.ir_type for v in values)
    if element_types != value_types:
        raise InternalError(
            f"unexpected types {value_types}: expected: {element_types}",
            value.source_location,
        )


def _expand_types(typ: IRType) -> Iterable[IRType]:
    if isinstance(typ, EncodedTupleType):
        for item in typ.elements:
            yield from _expand_types(item)
    else:
        yield typ


def _array_type(value: Value) -> ArrayType:
    if not isinstance(value.ir_type, ArrayType):
        raise InternalError("expected ArrayType: {value.ir_type}", value.source_location)
    return value.ir_type


@attrs.define(eq=False, kw_only=True)
class _ArrayOp(Op, ValueProvider):
    array: Value = attrs.field()
    # capture array type on the node, so the array value can be optimized
    # and still retain array type information
    array_type: ArrayType = attrs.field()

    @array_type.default
    def _array_type(self) -> ArrayType:
        return _array_type(self.array)


@attrs.define(eq=False)
class ArrayReadIndex(_ArrayOp):
    index: Value = attrs.field(validator=_is_uint64_type)

    @property
    def types(self) -> Sequence[IRType]:
        return encoded_ir_type_to_ir_types(self.array_type.element)

    def _frozen_data(self) -> object:
        return self.array, self.index

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_read_index(self)


@attrs.define(eq=False)
class ArrayWriteIndex(_ArrayOp):
    index: Value = attrs.field(validator=_is_uint64_type)
    value: "Value | ValueTuple" = attrs.field(validator=_value_has_encoded_array_element_type)

    def _frozen_data(self) -> object:
        return self.array, self.index, self.value

    @property
    def types(self) -> Sequence[IRType]:
        return (self.array_type,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_write_index(self)


@attrs.define(eq=False)
class ArrayConcat(_ArrayOp):
    """Concats two array values"""

    other: Value = attrs.field()

    def _frozen_data(self) -> object:
        return self.array, self.other

    @other.validator
    def _other_validator(self, _attr: object, other: Value) -> None:
        assert self.array.ir_type == other.ir_type

    @property
    def types(self) -> Sequence[IRType]:
        return (self.array_type,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_concat(self)


@attrs.define(eq=False)
class ArrayEncode(Op, ValueProvider):
    """Encodes a sequence of values into array_type"""

    values: Sequence[Value]
    array_type: ArrayType

    def _frozen_data(self) -> object:
        return self.values, self.array_type

    @property
    def types(self) -> Sequence[IRType]:
        return (self.array_type,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_encode(self)


@attrs.define(eq=False)
class ArrayPop(_ArrayOp):
    # TODO: maybe allow pop with an index?

    def _frozen_data(self) -> object:
        return self.array

    @property
    def types(self) -> Sequence[IRType]:
        return self.array_type, *encoded_ir_type_to_ir_types(self.array_type.element)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_pop(self)


@attrs.define(eq=False)
class ArrayLength(_ArrayOp):
    def _frozen_data(self) -> object:
        return self.array

    @property
    def types(self) -> Sequence[IRType]:
        return (PrimitiveIRType.uint64,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_length(self)


@attrs.define(eq=False)
class NewSlot(Op, ValueProvider):
    ir_type: SlotType = attrs.field(converter=_narrow_to_slot_type)

    def _frozen_data(self) -> object:
        return self.ir_type

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_new_slot(self)

    @property
    def types(self) -> Sequence[IRType]:
        return (self.ir_type,)


@attrs.define(eq=False)
class ReadSlot(Op, ValueProvider):
    slot: Value = attrs.field(validator=_is_slot_type)

    def _frozen_data(self) -> object:
        return self.slot

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_read_slot(self)

    @property
    def types(self) -> Sequence[IRType]:
        slot_type = self.slot.ir_type
        assert isinstance(slot_type, SlotType)
        return (slot_type.contents,)


@attrs.define(eq=False)
class WriteSlot(Op):
    slot: Value = attrs.field(validator=_is_slot_type)
    value: Value = attrs.field()
    source_location: SourceLocation | None

    def _frozen_data(self) -> object:
        return self.slot, self.value

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_write_slot(self)


@attrs.define(eq=False)
class Intrinsic(Op, ValueProvider):
    """Any TEAL op (or pseudo-op) that doesn't interrupt control flow, in the "basic block" sense.

    refs:
    - https://dev.algorand.co/reference/algorand-teal/opcodes/
    - https://dev.algorand.co/concepts/smart-contracts/avm/#assembler-syntax
    """

    op: AVMOp
    # TODO: consider treating ops with no args (only immediates) as Value types
    #       e.g. `txn NumAppArgs` or `txna ApplicationArgs 0`
    immediates: list[str | int] = attrs.field(factory=list)
    args: list[Value] = attrs.field(factory=list)
    error_message: str | None = None
    """If the program fails at this op, error_message will be displayed as the reason"""
    _types: Sequence[IRType] = attrs.field(converter=tuple[IRType, ...])

    @_types.default
    def _default_types(self) -> tuple[IRType, ...]:
        for ir_type in self.op_signature.returns:
            if ir_type == PrimitiveIRType.any or isinstance(ir_type, UnionType):
                raise InternalError(
                    f"Intrinsic op {self.op.name} requires return type information",
                    self.source_location,
                )
        return tuple(self.op_signature.returns)

    def _frozen_data(self) -> object:
        return self.op, tuple(self.immediates), tuple(self.args), self.error_message

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

    @immediates.validator
    def _validate_immediates(self, _attribute: object, immediates: list[int | str]) -> None:
        if len(self.op.immediate_types) != len(immediates):
            logger.error("Incorrect number of immediates", location=self.source_location)
            return
        for imm_type, imm in zip(self.op.immediate_types, immediates, strict=True):
            match imm_type:
                case ImmediateKind.uint8:
                    if not isinstance(imm, int) or not (0 <= imm <= 255):
                        logger.critical(
                            "Invalid immediate, expected value between 0 and 255",
                            location=self.source_location,
                        )
                case ImmediateKind.arg_enum:
                    if not isinstance(imm, str):
                        logger.critical(
                            "Invalid immediate, expected enum value",
                            location=self.source_location,
                        )
                case _:
                    typing.assert_never(imm_type)

    def _check_stack_types(
        self,
        context: str,
        expected_types: Sequence[IRType],
        source_types: Sequence[IRType],
    ) -> None:
        target_types = [a.avm_type for a in expected_types]
        if len(target_types) != len(source_types) or not all(
            tt & st.avm_type for tt, st in zip(target_types, source_types, strict=True)
        ):
            logger.error(
                (
                    f"incompatible {context} types on Intrinsic"
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
        return self.target.id, tuple(self.args)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_invoke_subroutine(self)

    @property
    def types(self) -> Sequence[IRType]:
        return self.target.returns


@attrs.define(eq=False)
class ValueTuple(ValueProvider):
    values: Sequence[Value]

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
    targets: Sequence[Register] = attrs.field(
        validator=[attrs.validators.min_len(1)], converter=tuple[Register, ...]
    )
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
                    f"incompatible types on assignment:"
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
    label: str | None = None
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
        return self.terminator.unique_targets

    @property
    def is_empty(self) -> bool:
        return not (self.phis or self.ops or self.terminator)

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
        return f"block@{self.id}"


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

    def _frozen_data(self) -> object:
        return self.value, tuple(b.id for b in self.blocks), self.default.id

    def targets(self) -> Sequence[BasicBlock]:
        return *self.blocks, self.default

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

    def _frozen_data(self) -> object:
        return (
            self.value,
            tuple((v, b.id) for v, b in self.cases.items()),
            self.default.id,
        )

    def targets(self) -> Sequence[BasicBlock]:
        return *self.cases.values(), self.default

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

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_program_exit(self)


@attrs.define(eq=False)
class Fail(ControlOp):
    """Exits immediately with a failure condition.

    assert statements with a compile time constant that is false
    should be translated to this node type in order to become ControlOp


    opcode: err
    """

    error_message: str | None

    def targets(self) -> Sequence[BasicBlock]:
        return ()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_fail(self)

    def _frozen_data(self) -> object:
        return self.error_message


@attrs.frozen
class Parameter(Register):
    implicit_return: bool


@attrs.define(eq=False, kw_only=True)
class Subroutine(Context):
    id: str
    short_name: str
    # source_location might be None if it was synthesized e.g. ARC-4 approval method
    source_location: SourceLocation | None
    parameters: Sequence[Parameter]
    _returns: Sequence[IRType]
    body: list[BasicBlock] = attrs.field()
    inline: bool | None

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
                    f"Unterminated block {block} assigned to subroutine {self.id}",
                    block.source_location,
                )
            for successor in block.successors:
                if block not in successor.predecessors:
                    # Note: this check is here rather than on BasicBlock only because of
                    # circular validation issues where you're trying to update the CFG by
                    # replacing a terminator
                    raise InternalError(
                        f"{block} does not appear in all {block.terminator}"
                        f" target's predecessor lists - missing from {successor.id} at least",
                        block.terminator.source_location
                        or block.source_location
                        or self.source_location,
                    )
            if not blocks.issuperset(block.predecessors):
                raise InternalError(
                    f"{block} of subroutine {self.id} has predecessor block(s) outside of list",
                    block.source_location,
                )
            if not blocks.issuperset(block.successors):
                raise InternalError(
                    f"{block} of subroutine {self.id} has predecessor block(s) outside of list",
                    block.source_location,
                )
            block_predecessors = dict.fromkeys(block.predecessors)
            for phi in block.phis:
                phi_blocks = dict.fromkeys(a.through for a in phi.args)
                if block_predecessors.keys() != phi_blocks.keys():
                    phi_block_labels = list(map(str, phi_blocks.keys()))
                    pred_block_labels = list(map(str, block_predecessors.keys()))
                    raise InternalError(
                        f"{self.id}: mismatch between phi predecessors ({phi_block_labels})"
                        f" and {block} predecessors ({pred_block_labels})"
                        f" for phi node {phi}",
                        self.source_location,
                    )
        used_registers = _get_used_registers(body)
        defined_registers = frozenset(self.parameters) | frozenset(_get_assigned_registers(body))
        bad_reads = used_registers - defined_registers
        if bad_reads:
            raise InternalError(
                f"The following variables are used but never defined:"
                f" {', '.join(map(str, bad_reads))}",
                self.source_location,
            )

    @property
    def entry(self) -> BasicBlock:
        return self.body[0]

    def get_assigned_registers(self) -> Iterator[Register]:
        yield from self.parameters
        yield from _get_assigned_registers(self.body)

    def get_used_registers(self) -> Iterator[Register]:
        yield from _get_used_registers(self.body)

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


def _get_assigned_registers(blocks: Sequence[BasicBlock]) -> Iterator[Register]:
    # TODO: replace with visitor
    for block in blocks:
        for phi in block.phis:
            yield phi.register
        for op in block.ops:
            if isinstance(op, Assignment):
                yield from op.targets


def _get_used_registers(blocks: Sequence[BasicBlock]) -> Set[Register]:
    from puya.ir.register_read_collector import RegisterReadCollector

    collector = RegisterReadCollector()
    for block in blocks:
        for op in block.all_ops:
            op.accept(collector)
    return collector.used_registers


class SlotAllocationStrategy(enum.StrEnum):
    none = enum.auto()
    dynamic = enum.auto()


@attrs.define(kw_only=True)
class SlotAllocation:
    reserved: Set[int]
    strategy: SlotAllocationStrategy


@attrs.define(kw_only=True, eq=False)
class Program(Context):
    """An individual TEAL output unit - e.g. an approval program, clear program, lsig"""

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
    kind: ProgramKind
    main: Subroutine
    subroutines: Sequence[Subroutine]
    avm_version: int
    slot_allocation: SlotAllocation
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
