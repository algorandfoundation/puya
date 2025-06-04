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
    @abc.abstractmethod
    def avm_type(self) -> AVMType: ...

    @property
    @abc.abstractmethod
    def maybe_avm_type(self) -> AVMType | str: ...

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    # TODO: consider removing this from IRType, as Encoding now covers a lot of what it used
    #       to provide
    #       May still be worth having SizedBytes, which can be used for types
    #       where the size can be statically guaranteed
    #       e.g. op code results, constants, and possibly values where the length has been checked
    #       via an assert
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


@attrs.frozen(str=False, order=False)
class TupleIRType:
    """
    Represents a tuple aggregate or an IRType

    Is not a subclass of IRType as it should only be used when it is explicitly required and
    handled
    """

    elements: Sequence["IRType | TupleIRType"] = attrs.field(
        converter=tuple["IRType | TupleIRType", ...]
    )

    @property
    def name(self) -> str:
        inner = ",".join(e.name for e in self.elements)
        return f"({inner},)"

    def __str__(self) -> str:
        return self.name

    @cached_property
    def arity(self) -> int:
        return sum(e.arity for e in self.elements)


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
    """Represents a slot containing a value of another type"""

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
    source_location: SourceLocation | None = None,
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
    allow_tuple: typing.Literal[True] = True,
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
