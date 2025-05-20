import abc
import enum
import typing
from collections.abc import Sequence
from functools import cached_property

import attrs

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.awst.nodes import BytesEncoding
from puya.awst.visitors import WTypeVisitor
from puya.errors import CodeError, InternalError
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
class AggregateIRType(IRType):
    elements: Sequence[IRType] = attrs.field(converter=tuple[IRType, ...])
    """Represents a type that is a combination of other types"""

    @property
    def name(self) -> str:
        inner = ",".join(e.name for e in self.elements)
        return f"({inner})"

    @property
    def avm_type(self) -> AVMType:
        raise InternalError("aggregate types cannot be mapped to an AVM stack type")

    @property
    def maybe_avm_type(self) -> str:
        return "aggregate"

    @property
    def num_bytes(self) -> int | None:
        return None

    def __str__(self) -> str:
        return self.name


# TODO: move encodings into their own file?
@attrs.frozen(str=False)
class Encoding(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def layout(self) -> str: ...

    @property
    @abc.abstractmethod
    def num_bytes(self) -> int | None: ...

    @cached_property
    def is_dynamic(self) -> bool:
        return self.num_bytes is None

    @cached_property
    def checked_num_bytes(self) -> int:
        assert self.num_bytes is not None, "expected statically sized type"
        return self.num_bytes

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False)
class BoolEncoding(Encoding):
    packable: bool
    num_bytes: int = attrs.field(default=1, init=False)

    @cached_property
    def name(self) -> str:
        if self.packable:
            return "bool_bit"
        else:
            return "bool"

    @property
    def layout(self) -> str:
        return self.name


@attrs.frozen(str=False)
class UIntEncoding(Encoding):
    n: int

    @cached_property
    def num_bytes(self) -> int:
        return self.n // 8

    @cached_property
    def name(self) -> str:
        return f"uint{self.n}"

    @property
    def layout(self) -> str:
        return self.name


@attrs.frozen(str=False)
class TupleEncoding(Encoding):
    elements: Sequence[Encoding] = attrs.field(converter=tuple[Encoding, ...])

    @cached_property
    def num_bytes(self) -> int | None:
        total_bits = 0
        for element in self.elements:
            if element.num_bytes is None:
                return None
            if isinstance(element, BoolEncoding) and element.packable:
                total_bits += 1
            else:
                # if not a bit packed bool, need to round up to byte boundary
                total_bits = bits_to_bytes(total_bits) * 8
                total_bits += element.num_bytes * 8

        total_bits = bits_to_bytes(total_bits) * 8
        return bits_to_bytes(total_bits)

    @cached_property
    def name(self) -> str:
        inner = ",".join(e.name for e in self.elements)
        return f"({inner})"

    @cached_property
    def layout(self) -> str:
        head = []
        tail = []
        for element in self.elements:
            if element.is_dynamic:
                head.append("offset")
                tail.append(element.layout)
            else:
                head.append(element.layout)
        inner = ",".join((*head, *tail))
        return f"({inner})"


@attrs.frozen(str=False)
class ArrayEncoding(Encoding):
    element: Encoding


@attrs.frozen(str=False)
class DynamicArrayEncoding(ArrayEncoding):
    length_header: bool = attrs.field()

    @cached_property
    def num_bytes(self) -> int | None:
        return None

    @cached_property
    def name(self) -> str:
        array = f"{self.element.name}[]"
        if self.length_header:
            return f"(len,{array})"
        else:
            return array

    @cached_property
    def layout(self) -> str:
        layouts = []
        # len header
        if self.length_header:
            layouts.append("len")

        # head
        if self.element.is_dynamic:
            layouts.append("offset[]")

        # tail
        layouts.append(f"{self.element.layout}[]")
        inner = ",".join(layouts)
        return f"({inner})"


@attrs.frozen(str=False)
class FixedArrayEncoding(ArrayEncoding):
    size: int

    @cached_property
    def num_bytes(self) -> int | None:
        if self.element.num_bytes is None:
            return None
        return self.element.num_bytes * self.size

    @cached_property
    def name(self) -> str:
        return f"{self.element.name}[{self.size}]"

    @cached_property
    def layout(self) -> str:
        layouts = []

        # head
        if self.element.is_dynamic:
            layouts.append(f"offset[{self.size}]")

        # tail
        layouts.append(f"{self.element.layout}[{self.size}]")
        inner = ",".join(layouts)
        return f"({inner})"


@attrs.frozen(str=False, order=False)
class EncodedType(IRType):
    encoding: Encoding

    @property
    def name(self) -> str:
        return f"Encoded({self.encoding.name})"

    @property
    def avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return self.avm_type

    @property
    def num_bytes(self) -> int | None:
        return self.encoding.num_bytes

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
    *,
    source_location: SourceLocation | None = None,
) -> IRType: ...


@typing.overload
def wtype_to_ir_type(
    wtype: wtypes.WType,
    /,
    source_location: SourceLocation,
    *,
    allow_aggregate: bool = False,
) -> IRType: ...


def wtype_to_ir_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    /,
    source_location: SourceLocation | None = None,
    *,
    allow_aggregate: bool = False,
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
        case wtypes.ReferenceArray():
            array_type = wtype_to_encoded_ir_type(wtype)
            return SlotType(array_type)
        case wtypes.ARC4Type() | wtypes.StackArray() | wtypes.account_wtype:
            return wtype_to_encoded_ir_type(wtype)
        case wtypes.WTuple(types=types) if allow_aggregate:
            return AggregateIRType(
                elements=[
                    wtype_to_ir_type(t, allow_aggregate=True, source_location=source_location)
                    for t in types
                ]
            )
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


class _WTypeToEncoding(WTypeVisitor[Encoding]):
    def visit_basic_type(self, wtype: wtypes.WType) -> Encoding:
        if wtype == wtypes.biguint_wtype:
            return UIntEncoding(n=64)
        elif wtype == wtypes.bool_wtype:
            return BoolEncoding(packable=True)
        elif wtype == wtypes.account_wtype:
            return UIntEncoding(n=32)
        if wtype.persistable:
            if wtype.scalar_type == AVMType.bytes:
                return wtypes.bytes_wtype.accept(self)
            elif wtype.scalar_type == AVMType.uint64:
                return UIntEncoding(n=64)
        self._unencodable(wtype)

    def visit_basic_arc4_type(self, wtype: wtypes.ARC4Type) -> Encoding:
        if wtype == wtypes.arc4_bool_wtype:
            return BoolEncoding(packable=True)
        self._unencodable(wtype)

    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> Encoding:
        return UIntEncoding(n=wtype.n)

    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> Encoding:
        return UIntEncoding(n=wtype.n)

    def visit_bytes_type(self, wtype: wtypes.BytesWType) -> Encoding:
        element = UIntEncoding(n=8)
        if wtype.length is None:
            return DynamicArrayEncoding(element=element, length_header=True)
        else:
            return TupleEncoding(elements=[element] * wtype.length)

    def visit_stack_array(self, wtype: wtypes.StackArray) -> Encoding:
        return DynamicArrayEncoding(element=wtype.element_type.accept(self), length_header=True)

    def visit_reference_array(self, wtype: wtypes.ReferenceArray) -> Encoding:
        element = wtype.element_type.accept(self)
        # top level bools can't be bit packed, due to no length header
        # only nested bools supported come from statically sized elements i.e.
        # fixed arrays or tuples, which can support bit packed bools
        if isinstance(element, BoolEncoding):
            element = BoolEncoding(packable=False)
        if element.is_dynamic:
            # TODO: is this actually a CodeError?
            raise InternalError("reference arrays can't have dynamic elements")
        return DynamicArrayEncoding(element=element, length_header=False)

    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> Encoding:
        return DynamicArrayEncoding(
            element=wtype.element_type.accept(self),
            length_header=True,
        )

    def visit_tuple_type(self, wtype: wtypes.WTuple) -> Encoding:
        return self._tuple_or_fixed_array(wtype)

    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> Encoding:
        return self._tuple_or_fixed_array(wtype)

    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> Encoding:
        return TupleEncoding(elements=[t.accept(self) for t in wtype.types])

    def _tuple_or_fixed_array(
        self, wtype: wtypes.WTuple | wtypes.ARC4Tuple | wtypes.ARC4Struct
    ) -> Encoding:
        try:
            (homogenous_type,) = set(wtype.types)
        except ValueError:
            return TupleEncoding(elements=[t.accept(self) for t in wtype.types])
        else:
            # describe homogenous tuples as fixed arrays for consistency
            return FixedArrayEncoding(
                element=homogenous_type.accept(self),
                size=len(wtype.types),
            )

    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> Encoding:
        return FixedArrayEncoding(
            element=wtype.element_type.accept(self),
            size=wtype.array_size,
        )

    def visit_enumeration_type(self, wtype: wtypes.WEnumeration) -> Encoding:
        self._unencodable(wtype)

    def visit_group_transaction_type(self, wtype: wtypes.WGroupTransaction) -> Encoding:
        # technically it could be encoded..., just not persisted
        self._unencodable(wtype)

    def visit_inner_transaction_type(self, wtype: wtypes.WInnerTransaction) -> Encoding:
        self._unencodable(wtype)

    def visit_inner_transaction_fields_type(
        self, wtype: wtypes.WInnerTransactionFields
    ) -> Encoding:
        self._unencodable(wtype)

    def _unencodable(self, wtype: wtypes.WType) -> typing.Never:
        raise InternalError(f"unencodable wtype: {wtype!s}")


class IRTypeAndEncoding(typing.NamedTuple):
    ir_type: IRType
    encoding: Encoding


def wtype_to_ir_type_and_encoding(wtype: wtypes.WType, loc: SourceLocation) -> IRTypeAndEncoding:
    return IRTypeAndEncoding(
        ir_type=wtype_to_ir_type(wtype, source_location=loc, allow_aggregate=True),
        encoding=wtype.accept(_WTypeToEncoding()),
    )


def wtype_to_encoding(wtype: wtypes.WType) -> Encoding:
    return wtype.accept(_WTypeToEncoding())


def wtype_to_encoded_ir_type(wtype: wtypes.WType) -> EncodedType:
    """
    Return the encoded IRType of a WType
    """
    return EncodedType(wtype_to_encoding(wtype))


def get_wtype_arity(wtype: wtypes.WType) -> int:
    """Returns the number of values this wtype represents on the stack"""
    if isinstance(wtype, wtypes.WTuple):
        return sum_wtypes_arity(wtype.types)
    else:
        return 1


def sum_wtypes_arity(types: Sequence[wtypes.WType]) -> int:
    return sum(map(get_wtype_arity, types))


def get_type_arity(ir_type: IRType) -> int:
    """Returns the number of values this wtype represents on the stack"""
    if isinstance(ir_type, AggregateIRType):
        return sum_types_arity(ir_type.elements)
    else:
        return 1


def sum_types_arity(types: Sequence[IRType]) -> int:
    return sum(map(get_type_arity, types))


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


def ir_type_to_ir_types(ir_type: IRType) -> list[IRType]:
    """
    Linearizes any AggregateIRType to a sequence of IRTypes

    Generally only useful in converting return types, use in other cases demands caution.
    """
    if isinstance(ir_type, AggregateIRType):
        return [ir_type for typ in ir_type.elements for ir_type in ir_type_to_ir_types(typ)]
    else:
        return [ir_type]
