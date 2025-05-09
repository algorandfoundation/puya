import abc
import enum
import typing
from collections.abc import Sequence

import attrs

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BytesEncoding
from puya.errors import CodeError, InternalError
from puya.ir.arc4 import get_arc4_static_bit_size, is_arc4_static_size
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes


@enum.unique
class AVMBytesEncoding(enum.StrEnum):
    unknown = enum.auto()
    base16 = enum.auto()
    base32 = enum.auto()
    base64 = enum.auto()
    utf8 = enum.auto()


# can't actually make this an ABC due to a conflict in metaclasses with enum.StrEnum
class IRType:
    @property
    @abc.abstractmethod
    def avm_type(self) -> AVMType: ...

    @property
    @abc.abstractmethod
    def maybe_avm_type(self) -> AVMType | str: ...

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def num_bytes(self) -> int | None:
        """Size of the type in bytes, None if the type is dynamically sized"""

    @typing.final
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, IRType):
            return NotImplemented
        # types are not super types of themselves
        if self == other:
            return False
        # any is a super type of all types
        if self == PrimitiveIRType.any:
            return True
        # bytes is a super type of other bytes types
        if self == PrimitiveIRType.bytes and other.maybe_avm_type == AVMType.bytes:
            return True
        # uint64 is a super type of other uint64 types
        if self == PrimitiveIRType.uint64 and other.maybe_avm_type == AVMType.uint64:  # noqa: SIM103
            return True
        else:
            return False

    @typing.final
    def __le__(self, other: object) -> bool:
        if not isinstance(other, IRType):
            return NotImplemented
        return self == other or self < other

    @typing.final
    def __gt__(self, other: object) -> bool:
        if not isinstance(other, IRType):
            return NotImplemented
        raise TypeError("types are partial ordered")

    @typing.final
    def __ge__(self, other: object) -> bool:
        if not isinstance(other, IRType):
            return NotImplemented
        raise TypeError("types are partial ordered")


@enum.unique
class PrimitiveIRType(IRType, enum.StrEnum):
    bytes = enum.auto()
    uint64 = enum.auto()
    bool = enum.auto()
    biguint = enum.auto()
    itxn_group_idx = enum.auto()  # the group index of the result
    itxn_field_set = enum.auto()  # a collection of fields for a pending itxn submit
    any = enum.auto()

    @property
    def name(self) -> str:
        return self._value_

    @property
    def avm_type(self) -> AVMType:
        maybe_result = self.maybe_avm_type
        if not isinstance(maybe_result, AVMType):
            raise InternalError(f"{maybe_result} cannot be mapped to AVM stack type")

        return maybe_result

    @property
    def maybe_avm_type(self) -> AVMType | str:
        match self:
            case PrimitiveIRType.uint64 | PrimitiveIRType.bool:
                return AVMType.uint64
            case PrimitiveIRType.bytes | PrimitiveIRType.biguint:
                return AVMType.bytes
            case PrimitiveIRType.any:
                return AVMType.any
            case PrimitiveIRType.itxn_group_idx | PrimitiveIRType.itxn_field_set:
                return self.name
            case _:
                raise InternalError(f"could not determine AVM type for {self.name}")

    @property
    def num_bytes(self) -> int | None:
        # a primitive bool is just a uint64 alias
        # encoded bools can have different sizes
        if self in (PrimitiveIRType.uint64, PrimitiveIRType.bool):
            return 8
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


@attrs.frozen(str=False, order=False)
class ArrayType(IRType):
    """An array of values encoded to a bytes value"""

    element: IRType

    @property
    def name(self) -> str:
        return f"{self.element.name}[]"

    @property
    def avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return self.avm_type

    @property
    def num_bytes(self) -> int | None:
        return None

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class EncodedTupleType(IRType):
    """A HLL tuple type encoded to a single bytes value"""

    elements: Sequence[IRType] = attrs.field(converter=tuple[IRType, ...])

    @property
    def name(self) -> str:
        elements = ",".join(e.name for e in self.elements)
        return f"({elements})"

    @property
    def avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return self.avm_type

    @property
    def num_bytes(self) -> int | None:
        total = 0
        for element in self.elements:
            if element.num_bytes is None:
                return None
            total += element.num_bytes
        return total

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class SlotType(IRType):
    """Represents a scratch slot containing a value of another type"""

    contents: IRType

    @property
    def name(self) -> str:
        return f"{self.contents.name}*"

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64]:
        return AVMType.uint64

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64]:
        return self.avm_type

    @property
    def num_bytes(self) -> int | None:
        return None

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class UnionType(IRType):
    """Union type, should generally only appear as an input type on AVM ops"""

    types: Sequence[IRType]

    @property
    def name(self) -> str:
        return "|".join(t.name for t in self.types)

    @property
    def avm_type(self) -> AVMType:
        try:
            (single_avm_type,) = {t.avm_type for t in self.types}
        except ValueError:
            return AVMType.any
        else:
            return single_avm_type

    @property
    def maybe_avm_type(self) -> AVMType:
        return self.avm_type

    @property
    def num_bytes(self) -> None:
        return None

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class EncodedUIntType(IRType):
    """"""

    original_type: IRType
    num_bytes: int

    @property
    def name(self) -> str:
        n = self.num_bytes * 8
        return f"encoded_uint{n}"

    @property
    def avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return self.avm_type

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class SizedBytesType(IRType):
    """A bytes type with a static length"""

    num_bytes: int

    @property
    def name(self) -> str:
        return f"bytes[{self.num_bytes}]"

    @property
    def avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return self.avm_type

    def __str__(self) -> str:
        return self.name


def bytes_enc_to_avm_bytes_enc(bytes_encoding: BytesEncoding) -> AVMBytesEncoding:
    try:
        return AVMBytesEncoding(bytes_encoding.value)
    except ValueError as ex:
        raise InternalError(f"Unhandled BytesEncoding: {bytes_encoding}") from ex


@typing.overload
def wtype_to_ir_type(
    expr: awst_nodes.Expression,
    /,
    source_location: SourceLocation | None = None,
) -> IRType: ...


@typing.overload
def wtype_to_ir_type(
    wtype: wtypes.WType,
    /,
    source_location: SourceLocation,
) -> IRType: ...


def wtype_to_ir_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    /,
    source_location: SourceLocation | None = None,
) -> IRType:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_ir_type(
            expr_or_wtype.wtype, source_location=source_location or expr_or_wtype.source_location
        )
    else:
        wtype = expr_or_wtype
        # static type analysis + typing.overload's above should prevent this
        assert source_location is not None, "unexpected empty SourceLocation"
    match wtype:
        case wtypes.bool_wtype:
            return PrimitiveIRType.bool
        case wtypes.biguint_wtype:
            return PrimitiveIRType.biguint
        case wtypes.BytesWType(length=l):
            return PrimitiveIRType.bytes if l is None else SizedBytesType(l)
        case wtypes.WInnerTransaction():
            return PrimitiveIRType.itxn_group_idx
        case wtypes.WInnerTransactionFields():
            return PrimitiveIRType.itxn_field_set
        # note: these exclusions are to maintain parity with what is supported
        #       between stack and reference arrays.
        #       ideally WGroupTransaction would work with either, but not be persistable
        #       inner transaction types are unlikely to be supported with current AVM restrictions
        case (
            wtypes.StackArray(element_type=element_type)
            | wtypes.ReferenceArray(element_type=element_type)
        ) if isinstance(
            element_type,
            wtypes.WGroupTransaction | wtypes.WInnerTransaction | wtypes.WInnerTransactionFields,
        ):
            raise CodeError("unsupported array element type", source_location)
        case wtypes.StackArray(element_type=element_wtype):
            element_ir_type = wtype_to_encoded_ir_type(
                element_wtype, require_static_size=False, loc=source_location
            )
            return ArrayType(element=element_ir_type)
        case wtypes.ReferenceArray(element_type=element_wtype):
            element_ir_type = wtype_to_encoded_ir_type(
                element_wtype, require_static_size=True, loc=source_location
            )
            array_type = ArrayType(element=element_ir_type)
            return SlotType(array_type)
        case wtypes.ARC4Type() as arc4_wtype if is_arc4_static_size(arc4_wtype):
            return SizedBytesType(bits_to_bytes(get_arc4_static_bit_size(arc4_wtype)))
        case wtypes.account_wtype:
            return SizedBytesType(num_bytes=32)
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
                f"unsupported nested/compound type encountered: {wtype}", source_location
            )
        case _:
            typing.assert_never(wtype.scalar_type)


def wtype_to_encoded_ir_type(
    wtype: wtypes.WType,
    *,
    require_static_size: bool,
    loc: SourceLocation,
) -> IRType:
    """
    Return the array encoded IRType of a WType
    """
    if isinstance(wtype, wtypes.WTuple):
        return EncodedTupleType(
            elements=[
                wtype_to_encoded_ir_type(e, require_static_size=require_static_size, loc=loc)
                for e in wtype.types
            ]
        )
    # note: any types added here should also be handled when lowering ArrayEncode nodes
    elif wtype == wtypes.bool_wtype:
        return EncodedUIntType(original_type=PrimitiveIRType.bool, num_bytes=1)
    elif wtype.scalar_type == AVMType.uint64:
        return EncodedUIntType(original_type=PrimitiveIRType.uint64, num_bytes=8)
    elif wtype == wtypes.biguint_wtype:
        return SizedBytesType(num_bytes=64)
    else:
        ir_type = wtype_to_ir_type(wtype, loc)
        if ir_type.num_bytes is None and require_static_size:
            raise CodeError("unsupported array element type", loc)
        return ir_type


def encoded_ir_type_to_ir_types(ir_type: IRType) -> Sequence[IRType]:
    if isinstance(ir_type, EncodedTupleType):
        return tuple(
            t for element in ir_type.elements for t in encoded_ir_type_to_ir_types(element)
        )
    if isinstance(ir_type, EncodedUIntType):
        ir_type = ir_type.original_type
    return (ir_type,)


def expand_encoded_type_and_group(ir_type: IRType) -> Sequence[tuple[IRType, int]]:
    """
    Returns a sequence of (type, group_id) values.
    Where group_id is an int representing the original tuple they were part of.
    Items from the same tuple will have the same id.

    e.g.
    bool,(bool,bool),(bool,bool),bool
    will return
    [(bool,1),(bool,2),(bool,2),(bool,3),(bool,3),(bool,1)]
    """
    group = idx = 0
    result = [(ir_type, group)]
    while idx < len(result):
        typ = result[idx][0]
        if isinstance(typ, EncodedTupleType):
            group += 1
            result[idx : idx + 1] = [(e, group) for e in typ.elements]
        else:
            idx += 1
    return result


def get_wtype_arity(wtype: wtypes.WType) -> int:
    """Returns the number of values this wtype represents on the stack"""
    if isinstance(wtype, wtypes.WTuple):
        return sum_wtypes_arity(wtype.types)
    else:
        return 1


def sum_wtypes_arity(types: Sequence[wtypes.WType]) -> int:
    return sum(map(get_wtype_arity, types))


def wtype_to_ir_types(wtype: wtypes.WType, source_location: SourceLocation) -> list[IRType]:
    """
    Similar to wtype_to_ir_type, except:
      - tuples will be expanded (recursively, if nested)
      - void will be treated as "empty"

    Generally only useful in converting return types, use in other cases demands caution.
    """
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
