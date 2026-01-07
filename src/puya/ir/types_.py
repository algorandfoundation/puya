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
from puya.ir.encodings import Encoding, wtype_to_encoding
from puya.parse import SourceLocation


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
    def avm_type(self) -> AVMType:
        maybe_result = self.maybe_avm_type
        if isinstance(maybe_result, str):
            raise InternalError(f"{maybe_result} cannot be mapped to AVM stack type")

        return maybe_result

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

    @typing.final
    @property
    def arity(self) -> int:
        return 1


@enum.unique
class PrimitiveIRType(IRType, enum.StrEnum):
    bytes = enum.auto()
    uint64 = enum.auto()
    string = enum.auto()
    bool = enum.auto()
    account = enum.auto()
    biguint = enum.auto()
    itxn_group_idx = enum.auto()  # the group index of the result
    itxn_field_set = enum.auto()  # a collection of fields for a pending itxn submit
    any = enum.auto()

    @property
    def name(self) -> str:
        return self._value_

    @property
    def maybe_avm_type(self) -> AVMType | str:
        match self:
            case PrimitiveIRType.uint64 | PrimitiveIRType.bool:
                return AVMType.uint64
            case (
                PrimitiveIRType.account
                | PrimitiveIRType.bytes
                | PrimitiveIRType.biguint
                | PrimitiveIRType.string
            ):
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
        if self == PrimitiveIRType.account:
            return 32
        return None

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"


bytes_: typing.Final = PrimitiveIRType.bytes
uint64: typing.Final = PrimitiveIRType.uint64
string: typing.Final = PrimitiveIRType.string
bool_: typing.Final = PrimitiveIRType.bool
account: typing.Final = PrimitiveIRType.account
biguint: typing.Final = PrimitiveIRType.biguint
itxn_group_idx: typing.Final = PrimitiveIRType.itxn_group_idx
itxn_field_set: typing.Final = PrimitiveIRType.itxn_field_set
any_: typing.Final = PrimitiveIRType.any


@attrs.frozen(str=False, order=False)
class TupleIRType:
    """
    Represents a tuple aggregate or an IRType

    Is not a subclass of IRType as it should only be used when it is explicitly required and
    handled
    """

    elements: tuple["IRType | TupleIRType", ...] = attrs.field(
        converter=tuple["IRType | TupleIRType", ...]
    )
    fields: tuple[str, ...] | None = attrs.field()

    @fields.validator
    def _validate_fields(self, _: object, fields: tuple[str, ...] | None) -> None:
        if fields is not None and len(fields) != len(self.elements):
            raise InternalError("length mismatch between TupleIRType element types and names")

    @property
    def name(self) -> str:
        inner = ",".join(e.name for e in self.elements)
        return f"({inner},)"

    def __str__(self) -> str:
        return self.name

    @cached_property
    def arity(self) -> int:
        return sum(e.arity for e in self.elements)

    def build_item_names(self, base_name: str) -> list[str]:
        result = list[str]()
        if self.fields is None:
            for idx, typ in enumerate(self.elements):
                sub_name = f"{base_name}.{idx}"
                if isinstance(typ, TupleIRType):
                    result.extend(typ.build_item_names(sub_name))
                else:
                    result.append(sub_name)
        else:
            for fname, typ in zip(self.fields, self.elements, strict=True):
                sub_name = f"{base_name}.{fname}"
                if isinstance(typ, TupleIRType):
                    result.extend(typ.build_item_names(sub_name))
                else:
                    result.append(sub_name)
        return result


@attrs.frozen(str=False, order=False)
class EncodedType(IRType):
    encoding: Encoding

    @property
    def name(self) -> str:
        name = self.encoding.name
        if name.startswith("(") and name.endswith(")"):
            name = name[1:-1]
        return f"Encoded({name})"

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes, AVMType.uint64]:
        if self.encoding.is_bit:
            return AVMType.uint64
        else:
            return AVMType.bytes

    @property
    def num_bytes(self) -> int | None:
        return self.encoding.num_bytes

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class SlotType(IRType):
    """Represents a slot containing a value of another type"""

    contents: IRType

    @property
    def name(self) -> str:
        return f"{self.contents.name}*"

    @property
    def maybe_avm_type(self) -> typing.Literal[AVMType.uint64]:
        return AVMType.uint64

    @property
    def num_bytes(self) -> int | None:
        return None

    def __str__(self) -> str:
        return self.name


@attrs.frozen(str=False, order=False)
class UnionType(IRType):
    """Union type, should generally only appear as an input type on AVM ops"""

    types: tuple[IRType, ...] = attrs.field(converter=tuple[IRType, ...])

    @property
    def name(self) -> str:
        return "|".join(t.name for t in self.types)

    @property
    def maybe_avm_type(self) -> AVMType:
        try:
            (single_avm_type,) = {t.avm_type for t in self.types}
        except ValueError:
            return AVMType.any
        else:
            return single_avm_type

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
    def maybe_avm_type(self) -> typing.Literal[AVMType.bytes]:
        return AVMType.bytes

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
    *,
    allow_tuple: bool = False,
) -> IRType: ...


@typing.overload
def wtype_to_ir_type(
    wtype: wtypes.WType,
    /,
    source_location: SourceLocation,
) -> IRType: ...


@typing.overload
def wtype_to_ir_type(
    wtype: wtypes.WTuple,
    /,
    source_location: SourceLocation,
    *,
    allow_tuple: typing.Literal[True] = True,
) -> TupleIRType: ...


@typing.overload
def wtype_to_ir_type(
    wtype: wtypes.WType,
    /,
    source_location: SourceLocation,
    *,
    allow_tuple: bool,
) -> IRType | TupleIRType: ...


def wtype_to_ir_type(
    expr_or_wtype: wtypes.WType | awst_nodes.Expression,
    /,
    source_location: SourceLocation | None = None,
    *,
    allow_tuple: bool = False,
) -> IRType | TupleIRType:
    if isinstance(expr_or_wtype, awst_nodes.Expression):
        return wtype_to_ir_type(
            expr_or_wtype.wtype,
            source_location=(source_location or expr_or_wtype.source_location),
            allow_tuple=allow_tuple,
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
        case wtypes.string_wtype:
            return PrimitiveIRType.string
        case wtypes.account_wtype:
            return PrimitiveIRType.account
        case wtypes.ReferenceArray():
            array_type = wtype_to_encoded_ir_type(wtype, source_location)
            return SlotType(array_type)
        case wtypes.ARC4Type():
            return wtype_to_encoded_ir_type(wtype, source_location)
        case wtypes.WTuple(types=types) if allow_tuple:
            return TupleIRType(
                elements=[
                    wtype_to_ir_type(t, allow_tuple=True, source_location=source_location)
                    for t in types
                ],
                fields=wtype.names,
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


def wtype_to_encoded_ir_type(wtype: wtypes.WType, loc: SourceLocation) -> EncodedType:
    """
    Return the encoded IRType of a WType
    """
    return EncodedType(wtype_to_encoding(wtype, loc))


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


def ir_type_to_ir_types(ir_type: IRType | TupleIRType) -> list[IRType]:
    """
    Linearizes any TupleIRType to a sequence of IRTypes

    Generally only useful in converting return types, use in other cases demands caution.
    """
    if isinstance(ir_type, TupleIRType):
        return [ir_type for typ in ir_type.elements for ir_type in ir_type_to_ir_types(typ)]
    else:
        return [ir_type]


def wtype_to_abi_name(
    wtype: wtypes.WType,
    *,
    resource_encoding: typing.Literal["index", "value"] = "value",
    source_location: SourceLocation,
) -> str:
    """
    Convert a WType to its ABI name representation
    """
    visitor = _WTypeToABIName(resource_encoding, source_location)
    return wtype.accept(visitor)


_RESOURCE_INDEX_TO_VALUE = {
    wtypes.account_wtype: wtypes.arc4_address_alias,
    wtypes.application_wtype: wtypes.uint64_wtype,
    wtypes.asset_wtype: wtypes.uint64_wtype,
}
_BASIC_TYPES_TO_ABI_NAME = {
    wtypes.account_wtype: "account",
    wtypes.application_wtype: "application",
    wtypes.asset_wtype: "asset",
    wtypes.biguint_wtype: "uint512",
    wtypes.bool_wtype: "bool",
    wtypes.uint64_wtype: "uint64",
    wtypes.string_wtype: "string",
    # address is not a basic type, but appears if account is mapped to a value type
    wtypes.arc4_address_alias: "address",
    wtypes.void_wtype: "void",
}


class _WTypeToABIName(WTypeVisitor[str]):
    def __init__(
        self,
        resource_encoding: typing.Literal["index", "value"],
        source_location: SourceLocation,
    ) -> None:
        self.loc = source_location
        self.resource_encoding = resource_encoding

    def visit_basic_type(self, wtype: wtypes.WType) -> str:
        if self.resource_encoding == "value":
            wtype = _RESOURCE_INDEX_TO_VALUE.get(wtype, wtype)

        try:
            return _BASIC_TYPES_TO_ABI_NAME[wtype]
        except KeyError:
            self._unencodable(wtype)

    def visit_basic_arc4_type(self, wtype: wtypes.ARC4Type) -> str:
        if wtype.arc4_alias is not None:
            return wtype.arc4_alias
        if wtype == wtypes.arc4_bool_wtype:
            return "bool"
        self._unencodable(wtype)

    def visit_arc4_uint(self, wtype: wtypes.ARC4UIntN) -> str:
        if wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"uint{wtype.n}"

    def visit_arc4_ufixed(self, wtype: wtypes.ARC4UFixedNxM) -> str:
        if wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"ufixed{wtype.n}x{wtype.m}"

    def visit_bytes_type(self, wtype: wtypes.BytesWType) -> str:
        if wtype.length is None:
            return "byte[]"
        else:
            return f"byte[{wtype.length}]"

    def visit_reference_array(self, wtype: wtypes.ReferenceArray) -> str:
        element = wtype.element_type.accept(self)
        return f"{element}[]"

    def visit_arc4_dynamic_array(self, wtype: wtypes.ARC4DynamicArray) -> str:
        if wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"{self._visit_in_aggregate(wtype.element_type)}[]"

    def visit_arc4_static_array(self, wtype: wtypes.ARC4StaticArray) -> str:
        if wtype.arc4_alias is not None:
            return wtype.arc4_alias
        return f"{self._visit_in_aggregate(wtype.element_type)}[{wtype.array_size}]"

    def visit_tuple_type(self, wtype: wtypes.WTuple) -> str:
        return f"({','.join(self._visit_in_aggregate(t) for t in wtype.types)})"

    def visit_arc4_tuple(self, wtype: wtypes.ARC4Tuple) -> str:
        typing.assert_type(wtype.arc4_alias, None)
        return f"({','.join(self._visit_in_aggregate(t) for t in wtype.types)})"

    def visit_arc4_struct(self, wtype: wtypes.ARC4Struct) -> str:
        typing.assert_type(wtype.arc4_alias, None)
        return f"({','.join(self._visit_in_aggregate(t) for t in wtype.types)})"

    def _visit_in_aggregate(self, wtype: wtypes.WType) -> str:
        return wtype.accept(self)

    def visit_enumeration_type(self, wtype: wtypes.WEnumeration) -> str:
        self._unencodable(wtype)

    def visit_group_transaction_type(self, wtype: wtypes.WGroupTransaction) -> str:
        if wtype.transaction_type is not None:
            return wtype.transaction_type.name
        else:
            return "txn"

    def visit_inner_transaction_type(self, wtype: wtypes.WInnerTransaction) -> str:
        self._unencodable(wtype)

    def visit_inner_transaction_fields_type(self, wtype: wtypes.WInnerTransactionFields) -> str:
        self._unencodable(wtype)

    def _unencodable(self, wtype: wtypes.WType) -> typing.Never:
        raise CodeError(f"unencodable type: {wtype}", self.loc)
