import abc
import copy
import enum
import typing
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
from puya.ir.encodings import ArrayEncoding, Encoding, TupleEncoding
from puya.ir.types_ import (
    AVMBytesEncoding,
    EncodedType,
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    SlotType,
    TupleIRType,
    UnionType,
    ir_type_to_ir_types,
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
T = typing.TypeVar("T")


class Context(typing.Protocol):
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


@attrs.frozen
class Value(ValueProvider, abc.ABC):
    """Base class for value types.

    This is anything that *is* a value, so excludes
    value *producers* such as subroutine invocations
    """

    ir_type: IRType = attrs.field(repr=lambda x: x.name)

    @property
    @typing.final
    def atype(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        atype = self.ir_type.avm_type
        if atype == AVMType.any:
            raise InternalError("unexpected any type", self.source_location)
        return atype

    @property
    def types(self) -> Sequence[IRType]:
        return (self.ir_type,)

    @typing.override
    @typing.final
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

    @abc.abstractmethod
    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        """Switch out target references to `find` with `replace`"""


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


@attrs.frozen
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


@attrs.frozen
class CompiledLogicSigReference(Value):
    artifact: LogicSigReference
    template_variables: Mapping[str, Value] = attrs.field(converter=immutabledict)
    source_location: SourceLocation | None = attrs.field(eq=False)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_compiled_logicsig_reference(self)


@attrs.frozen
class AddressConstant(Constant):
    """Constant for address literals"""

    ir_type: IRType = attrs.field(default=PrimitiveIRType.account, init=False)
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


@attrs.define(eq=False, kw_only=True)
class ArrayLength(ValueProvider):
    base: Value = attrs.field()
    # we retain the original type of the aggregate, in case this is lost during optimisations
    base_type: IRType = attrs.field(repr=lambda x: x.name)
    array_encoding: ArrayEncoding

    @property
    def types(self) -> Sequence[IRType]:
        return (PrimitiveIRType.uint64,)

    def _frozen_data(self) -> object:
        return self.base_type, self.base, self.array_encoding

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_array_length(self)


@attrs.define(eq=False, kw_only=True)
class _Aggregate(ValueProvider, abc.ABC):
    base: Value = attrs.field()
    # we retain the original type of the aggregate, in case this is lost during optimisations
    base_type: EncodedType = attrs.field(repr=lambda x: x.name)
    indexes: tuple[int | Value, ...] = attrs.field(
        validator=attrs.validators.min_len(1), converter=tuple[int | Value, ...]
    )

    @base_type.validator
    def _base_type_validator(self, _: object, base_type: EncodedType) -> None:
        if not isinstance(base_type.encoding, ArrayEncoding | TupleEncoding):
            raise InternalError(
                "unsupported aggregate encoding type for indexed read/write", self.source_location
            )


@attrs.define(eq=False)
class ExtractValue(_Aggregate):
    check_bounds: bool
    ir_type: IRType = attrs.field(repr=lambda x: x.name)

    @property
    def types(self) -> Sequence[IRType]:
        return (self.ir_type,)

    def _frozen_data(self) -> object:
        return self.base_type, self.base, self.indexes, self.check_bounds

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_extract_value(self)


@attrs.define(eq=False)
class ReplaceValue(_Aggregate):
    value: Value

    def _frozen_data(self) -> object:
        return self.base_type, self.base, self.indexes, self.value

    @property
    def types(self) -> Sequence[IRType]:
        return (self.base_type,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_replace_value(self)


@attrs.define(eq=False)
class BoxRead(ValueProvider):
    key: Value
    value_type: IRType
    exists_assertion_message: str

    def _frozen_data(self) -> object:
        return self.key, self.value_type

    @property
    def types(self) -> Sequence[IRType]:
        return (self.value_type,)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_box_read(self)


@attrs.define(eq=False)
class BoxWrite(Op):
    key: Value
    value: Value
    delete_first: bool
    source_location: SourceLocation | None

    def _frozen_data(self) -> object:
        return self.key, self.value, self.delete_first

    @property
    def types(self) -> Sequence[IRType]:
        return ()

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_box_write(self)


def _value_sequence(values: Sequence[Value]) -> list[Value]:
    return list(values)


@attrs.define(eq=False)
class BytesEncode(ValueProvider):
    """Encodes a sequence of values into encoded bytes"""

    source_location: SourceLocation = attrs.field(eq=False)
    encoding: Encoding
    values: list[Value] = attrs.field(converter=_value_sequence)
    values_type: IRType | TupleIRType = attrs.field()
    error_message_override: str | None = attrs.field(default=None, eq=False)

    @classmethod
    def maybe(
        cls,
        *,
        encoding: Encoding,
        values: Sequence[Value],
        values_type: IRType | TupleIRType,
        source_location: SourceLocation,
        error_message_override: str | None = None,
    ) -> ValueProvider:
        if isinstance(values_type, EncodedType) and values_type.encoding == encoding:
            (value,) = values
            return value
        return cls(
            source_location=source_location,
            encoding=encoding,
            values=values,
            values_type=values_type,
            error_message_override=error_message_override,
        )

    @values_type.validator
    def _value_type_validator(self, _: object, values_type: IRType | TupleIRType) -> None:
        if values_type.arity != len(self.values):
            raise InternalError(
                "expected values_type arity to match values arity", self.source_location
            )

    def _frozen_data(self) -> object:
        return tuple(self.values), self.values_type, self.encoding

    @property
    def types(self) -> Sequence[IRType]:
        return (EncodedType(self.encoding),)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_bytes_encode(self)


@attrs.define(eq=False)
class DecodeBytes(ValueProvider):
    """Decodes an encoded bytes into a sequence of values"""

    source_location: SourceLocation = attrs.field(eq=False)
    encoding: Encoding
    value: Value
    ir_type: IRType | TupleIRType = attrs.field()
    error_message_override: str | None = attrs.field(default=None, eq=False)

    @classmethod
    def maybe(
        cls,
        *,
        encoding: Encoding,
        value: Value,
        ir_type: IRType | TupleIRType,
        source_location: SourceLocation,
        error_message_override: str | None = None,
    ) -> ValueProvider:
        if isinstance(ir_type, EncodedType) and ir_type.encoding == encoding:
            return value
        return cls(
            source_location=source_location,
            encoding=encoding,
            value=value,
            ir_type=ir_type,
            error_message_override=error_message_override,
        )

    @ir_type.validator
    def _ir_type_type_validator(self, _: object, ir_type: IRType | TupleIRType) -> None:
        _arity_matches(ir_type, self.encoding, self.source_location)

    def _frozen_data(self) -> object:
        return self.value, self.encoding, self.ir_type

    @property
    def types(self) -> Sequence[IRType]:
        return ir_type_to_ir_types(self.ir_type)

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_decode_bytes(self)


def _arity_matches(
    ir_type: IRType | TupleIRType, encoding: Encoding, loc: SourceLocation | None
) -> None:
    match ir_type:
        case TupleIRType(elements=elements) if isinstance(encoding, TupleEncoding) and len(
            elements
        ) == len(encoding.elements):
            for element, encoding_element in zip(elements, encoding.elements, strict=False):
                _arity_matches(element, encoding_element, loc)
        case TupleIRType(elements=elements) if isinstance(encoding, ArrayEncoding) and len(
            elements
        ) == encoding.size:
            for element in elements:
                _arity_matches(element, encoding.element, loc)
        case TupleIRType():
            raise InternalError("type arity does not match encoding arity", loc)
        case _:
            pass


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
    values: list[Value] = attrs.field(converter=_value_sequence)
    ir_type: TupleIRType = attrs.field()

    @ir_type.default
    def _default_ir_type(self) -> TupleIRType:
        return TupleIRType(elements=[v.ir_type for v in self.values], fields=None)

    @ir_type.validator
    def _validate_arity(self, _: object, ir_type: TupleIRType) -> None:
        if ir_type.arity != len(self.values):
            raise InternalError(
                f"invalid type arity: {self.ir_type=}, {len(self.values)=}",
                self.source_location,
            )

    def accept(self, visitor: IRVisitor[T]) -> T:
        return visitor.visit_value_tuple(self)

    @property
    def types(self) -> Sequence[IRType]:
        return ir_type_to_ir_types(self.ir_type)

    def _frozen_data(self) -> object:
        return tuple(self.values)


MultiValue = Value | ValueTuple


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
    _predecessors: "dict[BasicBlock, None]" = attrs.field(factory=dict)
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

    def add_predecessor(self, predecessor: "BasicBlock") -> None:
        self._predecessors[predecessor] = None

    def discard_predecessor(self, predecessor: "BasicBlock") -> bool:
        try:
            self._predecessors.pop(predecessor)
        except KeyError:
            return False
        else:
            return True

    def remove_predecessor(self, predecessor: "BasicBlock") -> bool:
        if not self.discard_predecessor(predecessor):
            return False
        if self.phis:
            for phi in self.phis:
                for arg_idx, phi_arg in enumerate(phi.args):
                    if phi_arg.through == predecessor:
                        phi.args.pop(arg_idx)
                        break
                else:
                    raise InternalError(
                        "inconsistency between phi operands and predecessors", self.source_location
                    )
            if len(self.predecessors) == 1:
                targets = []
                source_values = []
                for phi in self.phis:
                    targets.append(phi.register)
                    (phi_arg,) = phi.args
                    source_values.append(phi_arg.value)
                loc = None  # phis have no location
                # phi nodes execute in parallel, so construct a single assignment
                source: ValueProvider
                try:
                    (source,) = source_values
                except ValueError:
                    source = ValueTuple(values=source_values, source_location=loc)
                copies = Assignment(targets=targets, source=source, source_location=loc)
                self.ops.insert(0, copies)
                self.phis.clear()
        return True

    def replace_predecessor(self, *, old: "BasicBlock", new: "BasicBlock") -> None:
        self._predecessors.pop(old)
        for phi in self.phis:
            for phi_arg in phi.args:
                if phi_arg.through == old:
                    phi_arg.through = new
                    break
            else:
                raise InternalError(
                    "inconsistency between phi operands and predecessors", self.source_location
                )
        self.add_predecessor(new)
        logger.debug(f"Replaced predecessor {old} with {new} in {self}")

    def set_predecessors(self, predecessors: Iterable["BasicBlock"]) -> None:
        self._predecessors = dict.fromkeys(predecessors)

    @property
    def predecessors(self) -> Set["BasicBlock"]:
        return self._predecessors.keys()

    @property
    def is_empty(self) -> bool:
        return not (self.phis or self.ops or self.terminator)

    @property
    def all_ops(self) -> list[Phi | Op | ControlOp]:
        result: list[Phi | Op | ControlOp] = [*self.phis, *self.ops]
        if self.terminator is not None:
            result.append(self.terminator)
        return result

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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        if self.non_zero is find:
            self.non_zero = replace
        if self.zero is find:
            self.zero = replace


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        if self.target is find:
            self.target = replace


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        for index, block in enumerate(self.blocks):
            if block is find:
                self.blocks[index] = replace
        if self.default is find:
            self.default = replace


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        for case, target in self.cases.items():
            if target is find:
                self.cases[case] = replace
        if self.default is find:
            self.default = replace


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        pass


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        pass


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

    def replace_target(self, *, find: "BasicBlock", replace: "BasicBlock") -> None:
        pass


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
    is_routing_wrapper: bool = False
    pure: bool = False

    @property
    def returns(self) -> list[IRType]:
        return [*self.explicit_returns, *self.implicit_returns]

    @property
    def explicit_returns(self) -> Sequence[IRType]:
        return self._returns

    @property
    def implicit_returns(self) -> tuple[IRType, ...]:
        return tuple(p.ir_type for p in self.parameters if p.implicit_return)

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
            for phi in block.phis:
                phi_blocks = dict.fromkeys(a.through for a in phi.args)
                if block.predecessors != phi_blocks.keys():
                    phi_block_labels = list(map(str, phi_blocks.keys()))
                    pred_block_labels = list(map(str, block.predecessors))
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

    def __deepcopy__(self, memo: dict[int, object]) -> object:
        # custom deep copy implementation to ensure stack limits are not hit with long
        # basic block call graphs
        memo[id(self)] = sub = attrs.evolve(self, body=[])

        for block in self.body:
            memo[id(block)] = block_copy = BasicBlock(
                id=block.id,
                label=block.label,
                comment=block.comment,
                source_location=block.source_location,
            )
            sub.body.append(block_copy)

        for block, block_copy in zip(self.body, sub.body, strict=True):
            block_copy.terminator = copy.deepcopy(block.terminator, memo)
            block_copy.phis[:] = copy.deepcopy(block.phis, memo)
            block_copy.ops[:] = copy.deepcopy(block.ops, memo)
            block_copy._predecessors = copy.deepcopy(block._predecessors, memo)  # noqa: SLF001
        attrs.validate(sub)
        return sub


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
    collector.visit_all_blocks(blocks)
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

    def all_programs(self) -> Iterable[Program]:
        return [self.approval_program, self.clear_program]


@attrs.define(eq=False)
class LogicSignature(Context):
    source_location: SourceLocation
    program: Program
    metadata: LogicSignatureMetaData

    def all_programs(self) -> Iterable[Program]:
        return [self.program]


ModuleArtifact = Contract | LogicSignature
