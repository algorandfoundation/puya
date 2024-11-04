import enum
import typing
from collections.abc import Sequence

import attrs

from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BytesEncoding
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops_models import StackType
from puya.parse import SourceLocation


@enum.unique
class AVMBytesEncoding(enum.StrEnum):
    unknown = enum.auto()
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    utf8 = enum.auto()


@typing.runtime_checkable
class IRType(typing.Protocol):
    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]: ...

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str: ...

    @property
    def name(self) -> str: ...

    @property
    def size(self) -> int | None:
        """Size of the type in bytes, None if the type is dynamically sized"""


@enum.unique
class PrimitiveIRType(enum.StrEnum):
    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        maybe_result = self.maybe_avm_type
        if not isinstance(maybe_result, AVMType):
            raise InternalError(f"{maybe_result} cannot be mapped to AVM stack type")
        return maybe_result

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        match self:
            case PrimitiveIRType.uint64 | PrimitiveIRType.bool:
                return AVMType.uint64
            case PrimitiveIRType.bytes | PrimitiveIRType.biguint:
                return AVMType.bytes
            case PrimitiveIRType.itxn_group_idx | PrimitiveIRType.itxn_field_set:
                return self.name
            case _:
                raise InternalError(f"could not determine AVM type for {self.name}")

    @property
    def size(self) -> int | None:
        match self:
            case PrimitiveIRType.uint64:
                return 8
            # TODO: make bools more efficient by bit packing them
            case PrimitiveIRType.bool:
                return 8
        return None

    bytes = enum.auto()
    uint64 = enum.auto()
    bool = enum.auto()
    biguint = enum.auto()
    itxn_group_idx = enum.auto()  # the group index of the result
    itxn_field_set = enum.auto()  # a collection of fields for a pending itxn submit


def bytes_enc_to_avm_bytes_enc(bytes_encoding: BytesEncoding) -> AVMBytesEncoding:
    try:
        return AVMBytesEncoding(bytes_encoding.value)
    except ValueError as ex:
        raise InternalError(f"Unhandled BytesEncoding: {bytes_encoding}") from ex


@attrs.frozen(str=False)
class ArrayType(IRType):
    element: IRType

    @property
    def name(self) -> str:
        return f"{self.element.name}[]"

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        return AVMType.bytes

    @property
    def size(self) -> int | None:
        return None

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False)
class EncodedTupleType(IRType):
    """A HLL tuple type encoded to a single bytes value"""

    elements: Sequence[IRType] = attrs.field(converter=tuple[IRType, ...])

    @property
    def name(self) -> str:
        elements = ",".join(e.name for e in self.elements)
        return f"({elements})"

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        return AVMType.bytes

    @property
    def size(self) -> int | None:
        total = 0
        for element in self.elements:
            if element.size is None:
                return None
            total += element.size
        return total

    @classmethod
    def expand_types(cls, ir_type: IRType) -> Sequence[IRType]:
        if isinstance(ir_type, cls):
            return tuple(t for element in ir_type.elements for t in cls.expand_types(element))
        return (ir_type,)

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False)
class SlotType(IRType):
    contents: IRType

    @property
    def name(self) -> str:
        return f"{self.contents.name}*"

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        return AVMType.uint64

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        return AVMType.uint64

    @property
    def size(self) -> int | None:
        return PrimitiveIRType.uint64.size

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False)
class FixedBytesType(IRType):
    _size: int

    @property
    def name(self) -> str:
        return f"bytes[{self.size}]"

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes] | str:
        return AVMType.bytes

    @property
    def size(self) -> int:
        return self._size

    def __str__(self) -> str:
        return self.name


def wtype_to_ir_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> IRType:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_ir_type(
            expr_or_wtype.wtype, source_location=source_location or expr_or_wtype.source_location
        )
    else:
        wtype = expr_or_wtype
    match wtype:
        case wtypes.bool_wtype:
            return PrimitiveIRType.bool
        case wtypes.biguint_wtype:
            return PrimitiveIRType.biguint
        case wtypes.WInnerTransaction():
            return PrimitiveIRType.itxn_group_idx
        case wtypes.WInnerTransactionFields():
            return PrimitiveIRType.itxn_field_set
        case wtypes.WArray(element_type=element_wtype):
            element_ir_type = wtype_to_encoded_ir_type(element_wtype, source_location)
            return SlotType(ArrayType(element=element_ir_type))
        # TODO: other fixed sized types
        case wtypes.ARC4UIntN(n=n) | wtypes.ARC4UFixedNxM(n=n):
            return FixedBytesType(size=n // 8)
        case wtypes.arc4_address_alias | wtypes.account_wtype:
            return FixedBytesType(size=32)
        case wtypes.void_wtype:
            raise InternalError("can't translate void wtype to irtype", source_location)
        # case wtypes.state_key:
        #     return IRType.state_key  # TODO
        # case wtypes.box_key:
        #     return IRType.box_key  # TODO
    match wtype.scalar_type:
        case AVMType.uint64:
            return PrimitiveIRType.uint64
        case AVMType.bytes:
            return PrimitiveIRType.bytes
        case None:
            raise CodeError(
                f"unsupported nested/compound wtype encountered: {wtype}", source_location
            )
        case _:
            typing.assert_never(wtype.scalar_type)


def wtype_to_encoded_ir_type(
    wtype: wtypes.WType,
    source_location: SourceLocation | None = None,
) -> IRType:
    if isinstance(wtype, wtypes.WTuple):
        return EncodedTupleType(elements=[wtype_to_encoded_ir_type(e) for e in wtype.types])
    else:
        return wtype_to_ir_type(wtype, source_location)


def get_wtype_arity(wtype: wtypes.WType) -> int:
    """Returns the number of values this wtype represents on the stack"""
    if isinstance(wtype, wtypes.WTuple):
        return sum_wtypes_arity(wtype.types)
    else:
        return 1


def sum_wtypes_arity(types: Sequence[wtypes.WType]) -> int:
    return sum(map(get_wtype_arity, types))


def wtype_to_ir_types(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    source_location: SourceLocation | None = None,
) -> list[IRType]:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        wtype = expr_or_wtype.wtype
    else:
        wtype = expr_or_wtype
    if wtype == wtypes.void_wtype:
        return []
    elif isinstance(wtype, wtypes.WTuple):
        return [
            ir_type
            for wtype in wtype.types
            for ir_type in wtype_to_ir_types(wtype, source_location)
        ]
    else:
        return [wtype_to_ir_type(wtype, source_location)]


def stack_type_to_avm_type(stack_type: StackType) -> AVMType:
    match stack_type:
        case StackType.uint64 | StackType.bool | StackType.asset | StackType.application:
            return AVMType.uint64
        case (
            StackType.bytes
            | StackType.bigint
            | StackType.box_name
            | StackType.address
            | StackType.state_key
        ):
            return AVMType.bytes
        case StackType.any | StackType.address_or_index:
            return AVMType.any


def stack_type_to_ir_type(stack_type: StackType) -> IRType | None:
    match stack_type:
        case StackType.bool:
            return PrimitiveIRType.bool
        case StackType.bigint:
            return PrimitiveIRType.biguint
        case StackType.uint64 | StackType.asset | StackType.application:
            return PrimitiveIRType.uint64
        case StackType.bytes | StackType.box_name | StackType.address | StackType.state_key:
            return PrimitiveIRType.bytes
        case StackType.any | StackType.address_or_index:
            return None
        case _:
            typing.assert_never(stack_type)
