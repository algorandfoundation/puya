import abc
import typing
from collections.abc import Sequence
from functools import cached_property

import attrs

from puya.avm import AVMType
from puya.awst import wtypes
from puya.awst.visitors import WTypeVisitor
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes, round_bits_to_nearest_bytes


@attrs.frozen(str=False)
class Encoding(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def num_bits(self) -> int | None: ...

    @cached_property
    @typing.final
    def num_bytes(self) -> int | None:
        bits = self.num_bits
        if bits is None:
            return None
        return bits_to_bytes(bits)

    @cached_property
    @typing.final
    def is_dynamic(self) -> bool:
        return self.num_bytes is None

    @cached_property
    @typing.final
    def is_fixed(self) -> bool:
        return self.num_bytes is not None

    @cached_property
    @typing.final
    def is_bit(self) -> bool:
        return self.num_bits == 1

    @cached_property
    @typing.final
    def checked_num_bytes(self) -> int:
        assert self.num_bytes is not None, "expected statically sized type"
        return self.num_bytes

    @cached_property
    @typing.final
    def checked_num_bits(self) -> int:
        assert self.num_bits is not None, "expected statically sized type"
        return self.num_bits

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False)
class BoolEncoding(Encoding):
    @cached_property
    def num_bits(self) -> int:
        return 1

    @cached_property
    def name(self) -> str:
        return "bool1"


@attrs.frozen(str=False)
class UIntEncoding(Encoding):
    n: int

    @cached_property
    def num_bits(self) -> int:
        return self.n

    @cached_property
    def name(self) -> str:
        return f"uint{self.n}"


@attrs.frozen(str=False)
class UTF8Encoding(Encoding):
    @cached_property
    def num_bits(self) -> int:
        return 8

    @cached_property
    def name(self) -> str:
        return "utf8"


@attrs.frozen(str=False)
class TupleEncoding(Encoding):
    elements: Sequence[Encoding] = attrs.field(converter=tuple[Encoding, ...])
    names: Sequence[str] | None = attrs.field(default=None, eq=False)

    @names.validator
    def _names_validator(self, _: object, value: Sequence[str] | None) -> None:
        if value is None:
            return
        if len(value) != len(self.elements):
            raise InternalError("expected names to match elements if provided")

    def get_head_bit_offset(self, index: int | None) -> int:
        bit_size = 0
        for encoding in self.elements[:index]:
            # may need to round to the next byte if bit-packing has ended
            if not encoding.is_bit:
                bit_size = round_bits_to_nearest_bytes(bit_size)
            if encoding.is_dynamic:
                bit_size += 16
            else:
                bit_size += encoding.checked_num_bits
        return bit_size

    @cached_property
    def num_bits(self) -> int | None:
        total_bits = 0
        for element in self.elements:
            if element.num_bytes is None:
                return None
            if isinstance(element, BoolEncoding):
                total_bits += 1
            else:
                # if not a bit packed bool, need to round up to byte boundary
                total_bits = bits_to_bytes(total_bits) * 8
                total_bits += element.num_bytes * 8

        total_bits = bits_to_bytes(total_bits) * 8
        return total_bits

    @cached_property
    def name(self) -> str:
        inner = ",".join(e.name for e in self.elements)
        return f"({inner})"


@attrs.frozen(str=False)
class Bool8Encoding(TupleEncoding):
    elements: Sequence[Encoding] = attrs.field(default=(BoolEncoding(),), init=False)
    names: None = attrs.field(default=None, init=False, eq=False)

    @property
    def name(self) -> str:
        return "bool8"


@attrs.frozen(str=False)
class ArrayEncoding(Encoding, abc.ABC):
    element: Encoding
    size: int | None
    length_header: bool

    def __attrs_post_init__(self) -> None:
        if self.size is not None:
            if self.length_header:
                # we could support this scenario, even though it's redundant,
                # but it's never constructed currently
                raise InternalError(
                    "fixed size array encoding with length header is not supported"
                )
        else:  # array is runtime sized # noqa: PLR5501
            if self.length_header is None and self.element.is_dynamic:
                # this is an impossible scenario, we can only omit the length header
                # if we know the element size and can use that to divide the length
                raise InternalError(
                    "dynamically sized array must have static-sized elements or a length header"
                )

    @classmethod
    def dynamic(cls, element: Encoding, *, length_header: bool) -> typing.Self:
        return cls(
            element=element,
            size=None,
            length_header=length_header,
        )

    @classmethod
    def fixed(cls, element: Encoding, *, size: int) -> typing.Self:
        return cls(
            element=element,
            size=size,
            length_header=False,
        )

    @cached_property
    def name(self) -> str:
        if self.size is not None:
            array = f"{self.element.name}[{self.size}]"
        else:
            array = f"{self.element.name}[]"
        if self.length_header:
            return f"(len+{array})"
        else:
            return array

    @cached_property
    def num_bits(self) -> int | None:
        if (self.size is None) or (self.element.num_bits is None):
            return None
        return bits_to_bytes(self.element.num_bits * self.size) * 8


class _WTypeToEncoding(WTypeVisitor[Encoding]):
    def __init__(self, loc: SourceLocation | None) -> None:
        self.loc = loc

    def visit_basic_type(self, wtype: wtypes.WType) -> Encoding:
        if wtype == wtypes.biguint_wtype:
            return UIntEncoding(n=512)
        elif wtype == wtypes.bool_wtype:
            # bools are only packable when in a tuple sequence or as an array element
            return Bool8Encoding()
        elif wtype == wtypes.account_wtype:
            return wtypes.BytesWType(length=32).accept(self)
        elif wtype == wtypes.string_wtype:
            return wtypes.arc4_string_alias.accept(self)
        if wtype.persistable:
            if wtype.scalar_type == AVMType.bytes:
                return wtypes.bytes_wtype.accept(self)
            elif wtype.scalar_type == AVMType.uint64:
                return UIntEncoding(n=64)
        self._unencodable()

    def visit_basic_arc4_type(self, wtype: wtypes.ARC4Type) -> Encoding:
        if wtype == wtypes.arc4_bool_wtype:
            # bools are only packable when in a tuple sequence or as an array element
            return Bool8Encoding()
        self._unencodable()

    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> Encoding:
        return UIntEncoding(n=wtype.n)

    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> Encoding:
        return UIntEncoding(n=wtype.n)

    def visit_bytes_type(self, wtype: wtypes.BytesWType) -> Encoding:
        element = UIntEncoding(n=8)
        if wtype.length is None:
            return ArrayEncoding.dynamic(element=element, length_header=True)
        else:
            return ArrayEncoding.fixed(element=element, size=wtype.length)

    def visit_reference_array(self, wtype: wtypes.ReferenceArray) -> Encoding:
        element = wtype.element_type.accept(self)
        if element.is_dynamic:
            raise CodeError("reference arrays can't have dynamic elements", wtype.source_location)
        return ArrayEncoding.dynamic(element=element, length_header=False)

    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> Encoding:
        if wtype.arc4_alias == wtypes.arc4_string_alias.arc4_alias:
            return ArrayEncoding.dynamic(element=UTF8Encoding(), length_header=True)
        return ArrayEncoding.dynamic(
            element=self._visit_in_aggregate(wtype.element_type),
            length_header=True,
        )

    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> Encoding:
        return ArrayEncoding.fixed(
            element=self._visit_in_aggregate(wtype.element_type),
            size=wtype.array_size,
        )

    def visit_tuple_type(self, wtype: wtypes.WTuple) -> Encoding:
        return TupleEncoding(
            elements=[self._visit_in_aggregate(t) for t in wtype.types], names=wtype.names
        )

    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> Encoding:
        return TupleEncoding(elements=[self._visit_in_aggregate(t) for t in wtype.types])

    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> Encoding:
        return TupleEncoding(
            elements=[self._visit_in_aggregate(t) for t in wtype.types], names=wtype.names
        )

    def _visit_in_aggregate(self, wtype: wtypes.WType) -> Encoding:
        if wtype in (wtypes.bool_wtype, wtypes.arc4_bool_wtype):
            return BoolEncoding()
        else:
            return wtype.accept(self)

    def visit_enumeration_type(self, _: wtypes.WEnumeration) -> Encoding:
        self._unencodable()

    def visit_group_transaction_type(self, _: wtypes.WGroupTransaction) -> Encoding:
        # technically it could be encoded..., just not persisted
        self._unencodable()

    def visit_inner_transaction_type(self, _: wtypes.WInnerTransaction) -> Encoding:
        self._unencodable()

    def visit_inner_transaction_fields_type(self, _: wtypes.WInnerTransactionFields) -> Encoding:
        self._unencodable()

    def _unencodable(self) -> typing.Never:
        raise CodeError("unencodable type", self.loc)


@typing.overload
def wtype_to_encoding(
    wtype: wtypes.ARC4Array | wtypes.ReferenceArray, loc: SourceLocation | None
) -> ArrayEncoding: ...


@typing.overload
def wtype_to_encoding(
    wtype: wtypes.WTuple | wtypes.ARC4Tuple | wtypes.ARC4Struct, loc: SourceLocation | None
) -> TupleEncoding: ...


@typing.overload
def wtype_to_encoding(wtype: wtypes.WType, loc: SourceLocation | None) -> Encoding: ...


def wtype_to_encoding(wtype: wtypes.WType, loc: SourceLocation | None) -> Encoding:
    return wtype.accept(_WTypeToEncoding(loc))
