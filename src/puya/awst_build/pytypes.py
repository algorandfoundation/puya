from __future__ import annotations

import abc
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import cached_property

import attrs
import typing_extensions
from immutabledict import immutabledict

from puya import log
from puya.awst import wtypes
from puya.awst_build import constants
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

if typing.TYPE_CHECKING:
    from mypy.nodes import ArgKind

    from puya.awst_build.intrinsic_models import FunctionOpMapping, PropertyOpMapping

logger = log.get_logger(__name__)


# TODO: handle (somewhere) not allowing things like Box and BoxMap in tuples, arrays, etc


@attrs.frozen(kw_only=True, str=False)
class PyType(abc.ABC):
    name: str
    """The canonical fully qualified type name"""
    generic: PyType | None = None
    """The generic type that this type was parameterised from, if any."""
    bases: Sequence[PyType] = attrs.field(default=(), converter=tuple["PyType", ...])
    """Direct base classes. probably excluding the implicit builtins.object?"""
    mro: Sequence[PyType] = attrs.field(default=(), converter=tuple["PyType", ...])
    """All base cases, in Method Resolution Order"""

    @bases.validator
    def _bases_validate(self, _attribute: object, bases: Sequence[PyType]) -> None:
        if len(set(bases)) != len(bases):
            raise InternalError(f"Duplicate bases in {self}: [{', '.join(map(str, bases))}]")

    @mro.validator
    def _mro_validate(self, _attribute: object, mro: Sequence[PyType]) -> None:
        bases_missing_from_mro = set(self.bases).difference(mro)
        if bases_missing_from_mro:
            raise InternalError(
                f"Bases missing from MRO in {self}:"
                f" [{', '.join(map(str, bases_missing_from_mro))}]"
            )

    @cached_property
    def _friendly_name(self) -> str:
        """User-friendly fully-qualified name.

        Basically just strips "builtins." from types, and removes the private part
        of algopy names.
        """
        import re

        result, _ = re.subn(r"\bbuiltins\.", "", self.name)
        result, _ = re.subn(r"algopy\._[^.]+", "algopy", result)
        result = result.replace(NoneType.name, "None")
        return result

    def __str__(self) -> str:
        return self._friendly_name

    @property
    @abc.abstractmethod
    def wtype(self) -> wtypes.WType:
        """The WType that this type represents, if any."""

    def parameterise(
        self,
        args: Sequence[PyType],  # noqa: ARG002
        source_location: SourceLocation | None,
    ) -> PyType:
        """Produce parameterised type.
        Throws if not a generic type of if a parameterised generic type."""
        if self.generic:
            raise CodeError(f"Type already has parameters: {self}", source_location)
        raise CodeError(f"Not a generic type: {self}", source_location)


_builtins_registry: typing.Final = dict[str, PyType]()


_TPyType = typing_extensions.TypeVar("_TPyType", bound=PyType, default=PyType)


def _register_builtin(typ: _TPyType, *, alias: str | None = None) -> _TPyType:
    name = alias or typ.name
    existing_entry = _builtins_registry.get(name)
    if existing_entry is None:
        _builtins_registry[name] = typ
    elif existing_entry is typ:
        logger.debug(f"Duplicate registration of {typ}")
    else:
        raise InternalError(f"Duplicate mapping of {name}")
    return typ


def builtins_registry() -> dict[str, PyType]:
    """Get a copy of the builtins registry"""
    return _builtins_registry.copy()


# https://typing.readthedocs.io/en/latest/spec/literal.html#legal-and-illegal-parameterizations
# We don't support enums as typing.Literal parameters. mypy encodes these as str values with
# an additional "fallback" data member, but we don't need that complication.
# mypy.types.LiteralValue also includes float, noting its invalid as a parameterization, but
# we exclude this here.
# None types are also encoded as their own type, but we have them as values here.
TypingLiteralValue: typing.TypeAlias = int | bytes | str | bool | None
_TypeArgs: typing.TypeAlias = tuple[PyType, ...]
_Parameterise = typing_extensions.TypeAliasType(
    "_Parameterise",
    Callable[["_GenericType[_TPyType]", _TypeArgs, SourceLocation | None], _TPyType],
    type_params=(_TPyType,),
)


@typing.final
@attrs.frozen
class _GenericType(PyType, abc.ABC, typing.Generic[_TPyType]):
    """Represents a typing.Generic type with unknown parameters"""

    _parameterise: _Parameterise[_TPyType]
    _instance_cache: dict[_TypeArgs, _TPyType] = attrs.field(factory=dict, eq=False)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("Generic type usage requires parameters")

    @typing.override
    def parameterise(
        self, args: Sequence[PyType], source_location: SourceLocation | None
    ) -> _TPyType:
        return lazy_setdefault(
            self._instance_cache,
            key=tuple(args),
            default=lambda args_: self._parameterise(self, args_, source_location),
        )


def _parameterise_type_type(
    self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None  # noqa: ARG001
) -> TypeType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"Expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    return TypeType(typ=arg)


GenericTypeType: typing.Final[PyType] = _GenericType(
    name="builtins.type",
    parameterise=_parameterise_type_type,
)


@typing.final
@attrs.frozen
class TypeType(PyType):
    typ: PyType
    generic: PyType = attrs.field(default=GenericTypeType, init=False)
    name: str = attrs.field(init=False)

    @name.default
    def _name_default(self) -> str:
        return f"{self.generic.name}[{self.typ.name}]"

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("type objects are not usable as values")


@typing.final
@attrs.frozen
class TypingLiteralType(PyType):
    value: TypingLiteralValue
    source_location: SourceLocation | None
    name: str = attrs.field(init=False)
    generic: None = attrs.field(default=None, init=False)
    bases: Sequence[PyType] = attrs.field(default=(), init=False)
    mro: Sequence[PyType] = attrs.field(default=(), init=False)

    @name.default
    def _name_default(self) -> str:
        return f"typing.Literal[{self.value!r}]"

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is not usable as a value", self.source_location)


@typing.final
@attrs.frozen
class TupleType(PyType):
    generic: _GenericType[TupleType]
    items: tuple[PyType, ...] = attrs.field(validator=attrs.validators.min_len(1))
    wtype: wtypes.WType


@typing.final
@attrs.frozen
class ArrayType(PyType):
    items: PyType
    size: int | None
    wtype: wtypes.WType


@typing.final
@attrs.frozen
class StorageProxyType(PyType):
    content: PyType
    wtype: wtypes.WType


@typing.final
@attrs.frozen
class StorageMapProxyType(PyType):
    generic: PyType
    key: PyType
    content: PyType
    wtype: wtypes.WType


@typing.final
@attrs.frozen
class FuncArg:
    types: Sequence[PyType] = attrs.field(
        converter=tuple[PyType, ...], validator=attrs.validators.min_len(1)
    )
    name: str | None
    kind: ArgKind


@typing.final
@attrs.frozen(kw_only=True)
class FuncType(PyType):
    generic: None = None
    ret_type: PyType
    args: Sequence[FuncArg] = attrs.field(converter=tuple[FuncArg, ...])
    bound_arg_types: Sequence[PyType] = attrs.field(converter=tuple[PyType, ...])

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("function objects are not usable as values")


@typing.final
@attrs.frozen
class StaticType(PyType):
    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is only usable as a type and cannot be instantiated")


@typing.final
@attrs.frozen(init=False)
class StructType(PyType):
    fields: Mapping[str, PyType] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    frozen: bool
    wtype: wtypes.WType
    source_location: SourceLocation | None
    generic: None = None

    @cached_property
    def names(self) -> Sequence[str]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> Sequence[PyType]:
        return tuple(self.fields.values())

    def __init__(
        self,
        *,
        base: PyType,
        name: str,
        fields: Mapping[str, PyType],
        frozen: bool,
        source_location: SourceLocation | None,
    ):
        field_wtypes = {name: field_typ.wtype for name, field_typ in fields.items()}
        # TODO: this is a bit of a kludge
        wtype_cls: Callable[
            [Mapping[str, wtypes.WType], bool, SourceLocation | None], wtypes.WType
        ]
        if base is ARC4StructBaseType:
            wtype_cls = wtypes.ARC4Struct
        elif base is StructBaseType:
            wtype_cls = wtypes.WStructType
        else:
            raise InternalError(f"Unknown struct base type: {base}", source_location)
        wtype = wtype_cls(field_wtypes, frozen, source_location)
        self.__attrs_init__(
            bases=[base],
            mro=[base],
            name=name,
            wtype=wtype,
            fields=fields,
            frozen=frozen,
            source_location=source_location,
        )


@typing.final
@attrs.frozen
class _SimpleType(PyType):
    wtype: wtypes.WType

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@typing.final
@attrs.frozen
class _LiteralOnlyType(PyType):
    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"Python literals of type {self} cannot be used as runtime values")

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


NoneType: typing.Final[PyType] = _SimpleType(name="types.NoneType", wtype=wtypes.void_wtype)
BoolType: typing.Final[PyType] = _SimpleType(name="builtins.bool", wtype=wtypes.bool_wtype)
IntLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.int")
StrLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.str")
BytesLiteralType: typing.Final[PyType] = _LiteralOnlyType(name="builtins.bytes")

UInt64Type: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_UINT64,
    wtype=wtypes.uint64_wtype,
)
BigUIntType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BIGUINT,
    wtype=wtypes.biguint_wtype,
)
BytesType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_BYTES,
    wtype=wtypes.bytes_wtype,
)
StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_STRING,
    wtype=wtypes.string_wtype,
)
AccountType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ACCOUNT,
    wtype=wtypes.account_wtype,
)
AssetType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ASSET,
    wtype=wtypes.asset_wtype,
)
ApplicationType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_APPLICATION,
    wtype=wtypes.application_wtype,
)
BytesBackedType: typing.Final[PyType] = _SimpleType(
    name=f"{constants.ALGOPY_PREFIX}_primitives.BytesBacked",
    wtype=wtypes.bytes_wtype,
)

_register_builtin(UInt64Type, alias=constants.ENUM_CLS_ON_COMPLETE_ACTION)
_register_builtin(UInt64Type, alias=constants.ENUM_CLS_TRANSACTION_TYPE)
OpUpFeeSourceType: typing.Final[PyType] = _SimpleType(  # TODO: replace with alias as above
    name=constants.OP_UP_FEE_SOURCE,
    wtype=wtypes.uint64_wtype,
)

ARC4StringType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_STRING,
    wtype=wtypes.arc4_string_wtype,
)
ARC4BoolType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_ARC4_BOOL,
    wtype=wtypes.arc4_bool_wtype,
)


@attrs.frozen
class ARC4UIntNType(PyType):
    bits: int
    wtype: wtypes.WType
    native_type: PyType


def _require_int_literal(
    generic: _GenericType,
    type_arg: PyType,
    source_location: SourceLocation | None,
    *,
    position_qualifier: str = "",
) -> int:

    match type_arg:
        case TypingLiteralType(value=int(value)):
            return value
    if position_qualifier:
        position_qualifier = position_qualifier + " "
    raise CodeError(
        f"{generic} expects a typing.Literal[<int>] as a {position_qualifier}parameter",
        source_location,
    )


def _make_arc4_unsigned_int_parameterise(
    *, native_type: PyType, max_bits: int | None = None
) -> _Parameterise:
    def parameterise(
        self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UIntNType:
        try:
            (bits_t,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        bits = _require_int_literal(self, bits_t, source_location)
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"Max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[{bits_t.name}]"
        return ARC4UIntNType(
            generic=self,
            name=name,
            bits=bits,
            native_type=native_type,
            wtype=wtypes.ARC4UIntN(bits, source_location),
        )

    return parameterise


GenericARC4UIntNType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(native_type=UInt64Type, max_bits=64),
)
GenericARC4BigUIntNType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_BIG_UINTN,
    parameterise=_make_arc4_unsigned_int_parameterise(native_type=BigUIntType),
)


ARC4UIntN_Aliases: typing.Final = immutabledict[int, ARC4UIntNType](
    {
        (_bits := 2**_exp): _register_builtin(
            (GenericARC4UIntNType if _bits <= 64 else GenericARC4BigUIntNType).parameterise(
                [TypingLiteralType(value=_bits, source_location=None)], source_location=None
            ),
            alias=f"{constants.ARC4_PREFIX}UInt{_bits}",
        )
        for _exp in range(3, 10)
    }
)
ARC4ByteType: typing.Final = _register_builtin(
    ARC4UIntNType(
        generic=None,
        name=constants.CLS_ARC4_BYTE,
        wtype=wtypes.arc4_byte_type,
        bits=8,
        bases=[ARC4UIntN_Aliases[8]],
        mro=[ARC4UIntN_Aliases[8]],
        native_type=UInt64Type,
    )
)


@attrs.frozen
class ARC4UFixedNxMType(PyType):
    generic: _GenericType
    bits: int
    precision: int
    wtype: wtypes.WType


def _make_arc4_unsigned_fixed_parameterise(*, max_bits: int | None = None) -> _Parameterise:
    def parameterise(
        self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None
    ) -> ARC4UFixedNxMType:
        try:
            bits_t, precision_t = args
        except ValueError:
            raise CodeError(
                f"Expected two type parameters, got {len(args)} parameters", source_location
            ) from None
        bits = _require_int_literal(self, bits_t, source_location, position_qualifier="first")
        precision = _require_int_literal(
            self, precision_t, source_location, position_qualifier="second"
        )
        if (max_bits is not None) and bits > max_bits:
            raise CodeError(f"Max bit size of {self} is {max_bits}, got {bits}", source_location)

        name = f"{self.name}[{bits_t.name}, {precision_t.name}]"
        return ARC4UFixedNxMType(
            generic=self,
            name=name,
            bits=bits,
            precision=precision,
            wtype=wtypes.ARC4UFixedNxM(bits, precision, source_location),
        )

    return parameterise


GenericARC4UFixedNxMType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(max_bits=64),
)
GenericARC4BigUFixedNxMType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_BIG_UFIXEDNXM,
    parameterise=_make_arc4_unsigned_fixed_parameterise(),
)


def _make_tuple_parameterise(
    typ: Callable[[Iterable[wtypes.WType], SourceLocation | None], wtypes.WType]
) -> _Parameterise[TupleType]:
    def parameterise(
        self: _GenericType[TupleType], args: _TypeArgs, source_location: SourceLocation | None
    ) -> TupleType:
        item_wtypes = [arg.wtype for arg in args]
        name = f"{self.name}[{', '.join(pyt.name for pyt in args)}]"
        return TupleType(
            generic=self,
            name=name,
            items=tuple(args),
            wtype=typ(item_wtypes, source_location),
        )

    return parameterise


GenericTupleType: typing.Final = _GenericType(
    name="builtins.tuple",
    parameterise=_make_tuple_parameterise(wtypes.WTuple),
)

GenericARC4TupleType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_TUPLE,
    parameterise=_make_tuple_parameterise(wtypes.ARC4Tuple),
)


@typing.final
@attrs.frozen
class VariadicTupleType(PyType):
    items: PyType
    generic: _GenericType = attrs.field(default=GenericTupleType, init=False)
    bases: Sequence[PyType] = attrs.field(default=(), init=False)
    mro: Sequence[PyType] = attrs.field(default=(), init=False)
    name: str = attrs.field(init=False)

    @name.default
    def _name_factory(self) -> str:
        return f"{self.generic.name}[{self.items.name}, ...]"

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError("variadic tuples cannot be used as runtime values")


def _make_array_parameterise(
    typ: Callable[[wtypes.WType, SourceLocation | None], wtypes.WType]
) -> _Parameterise[ArrayType]:
    def parameterise(
        self: _GenericType[ArrayType], args: _TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            (arg,) = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        name = f"{self.name}[{arg.name}]"
        return ArrayType(
            generic=self,
            name=name,
            size=None,
            items=arg,
            wtype=typ(arg.wtype, source_location),
        )

    return parameterise


GenericArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARRAY,
    parameterise=_make_array_parameterise(wtypes.WArray),
)

GenericARC4DynamicArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_DYNAMIC_ARRAY,
    parameterise=_make_array_parameterise(wtypes.ARC4DynamicArray),
)
ARC4DynamicBytesType: typing.Final = _register_builtin(
    ArrayType(
        name=constants.CLS_ARC4_DYNAMIC_BYTES,
        wtype=wtypes.arc4_dynamic_bytes,
        size=0,
        items=ARC4ByteType,
        bases=[GenericARC4DynamicArrayType.parameterise([ARC4ByteType], source_location=None)],
        mro=[GenericARC4DynamicArrayType.parameterise([ARC4ByteType], source_location=None)],
    )
)


def _make_fixed_array_parameterise(
    typ: Callable[[wtypes.WType, int, SourceLocation | None], wtypes.WType]
) -> _Parameterise:
    def parameterise(
        self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None
    ) -> ArrayType:
        try:
            items, size_t = args
        except ValueError:
            raise CodeError(
                f"Expected a single type parameter, got {len(args)} parameters", source_location
            ) from None
        size = _require_int_literal(self, size_t, source_location, position_qualifier="second")
        if size < 0:
            raise CodeError("Array size should be non-negative", source_location)

        name = f"{self.name}[{items.name}, {size_t.name}]"
        return ArrayType(
            generic=self,
            name=name,
            size=size,
            items=items,
            wtype=typ(items.wtype, size, source_location),
        )

    return parameterise


GenericARC4StaticArrayType: typing.Final = _GenericType(
    name=constants.CLS_ARC4_STATIC_ARRAY,
    parameterise=_make_fixed_array_parameterise(wtypes.ARC4StaticArray),
)
ARC4AddressType: typing.Final = _register_builtin(
    ArrayType(
        name=constants.CLS_ARC4_ADDRESS,
        wtype=wtypes.arc4_address_type,
        size=32,
        generic=None,
        items=ARC4ByteType,
        bases=[
            GenericARC4StaticArrayType.parameterise(
                [ARC4ByteType, TypingLiteralType(value=32, source_location=None)],
                source_location=None,
            )
        ],
        mro=[
            GenericARC4StaticArrayType.parameterise(
                [ARC4ByteType, TypingLiteralType(value=32, source_location=None)],
                source_location=None,
            )
        ],
    )
)


def _storage_parameterise(
    self: _GenericType[StorageProxyType], args: _TypeArgs, source_location: SourceLocation | None
) -> StorageProxyType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"Expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    name = f"{self.name}[{arg.name}]"
    return StorageProxyType(
        generic=self,
        name=name,
        content=arg,
        wtype=wtypes.bytes_wtype,
    )


def _parameterise_storage_map(
    self: _GenericType[StorageMapProxyType],
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> StorageMapProxyType:
    try:
        key, content = args
    except ValueError:
        raise CodeError(
            f"Expected two type parameters, got {len(args)} parameters", source_location
        ) from None
    name = f"{self.name}[{key.name}, {content.name}]"
    return StorageMapProxyType(
        generic=self,
        name=name,
        key=key,
        content=content,
        wtype=wtypes.bytes_wtype,
    )


GenericGlobalStateType: typing.Final = _GenericType(
    name=constants.CLS_GLOBAL_STATE,
    parameterise=_storage_parameterise,
)
GenericLocalStateType: typing.Final = _GenericType(
    name=constants.CLS_LOCAL_STATE,
    parameterise=_storage_parameterise,
)
GenericBoxType: typing.Final = _GenericType(
    name=constants.CLS_BOX_PROXY,
    parameterise=_storage_parameterise,
)
BoxRefType: typing.Final = _register_builtin(
    StorageProxyType(
        name=constants.CLS_BOX_REF_PROXY,
        content=BytesType,
        wtype=wtypes.bytes_wtype,
        generic=None,
    )
)

GenericBoxMapType: typing.Final = _GenericType(
    name=constants.CLS_BOX_MAP_PROXY,
    parameterise=_parameterise_storage_map,
)


GroupTransactionBaseType: typing.Final[PyType] = _SimpleType(
    name=constants.CLS_TRANSACTION_BASE,
    wtype=wtypes.WGroupTransaction(name="group_transaction_base", transaction_type=None),
)


@attrs.frozen
class TransactionRelatedType(PyType):
    wtype: wtypes.WType
    transaction_type: constants.TransactionType | None
    """None implies "any" type"""

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


def _make_gtxn_type(kind: constants.TransactionType | None) -> TransactionRelatedType:
    if kind is None:
        cls_name = "Transaction"
    else:
        cls_name = f"{_TXN_TYPE_NAMES[kind]}Transaction"
    stub_name = f"{constants.ALGOPY_PREFIX}gtxn.{cls_name}"
    return TransactionRelatedType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WGroupTransaction.from_type(kind),
    )


def _make_itxn_fieldset_type(kind: constants.TransactionType | None) -> TransactionRelatedType:
    if kind is None:
        cls_name = "InnerTransaction"
    else:
        cls_name = _TXN_TYPE_NAMES[kind]
    stub_name = f"{constants.ALGOPY_PREFIX}itxn.{cls_name}"
    return TransactionRelatedType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WInnerTransactionFields.from_type(kind),
    )


def _make_itxn_result_type(kind: constants.TransactionType | None) -> TransactionRelatedType:
    if kind is None:
        cls_name = "InnerTransactionResult"
    else:
        cls_name = f"{_TXN_TYPE_NAMES[kind]}InnerTransaction"
    stub_name = f"{constants.ALGOPY_PREFIX}itxn.{cls_name}"
    return TransactionRelatedType(
        name=stub_name,
        transaction_type=kind,
        wtype=wtypes.WInnerTransaction.from_type(kind),
    )


_TXN_TYPE_NAMES: typing.Final[Mapping[constants.TransactionType, str]] = {
    constants.TransactionType.pay: "Payment",
    constants.TransactionType.keyreg: "KeyRegistration",
    constants.TransactionType.acfg: "AssetConfig",
    constants.TransactionType.axfer: "AssetTransfer",
    constants.TransactionType.afrz: "AssetFreeze",
    constants.TransactionType.appl: "ApplicationCall",
}

_all_txn_kinds: typing.Final[Sequence[constants.TransactionType | None]] = [
    None,
    *constants.TransactionType,
]
GroupTransactionTypes: typing.Final[
    Mapping[constants.TransactionType | None, TransactionRelatedType]
] = {kind: _make_gtxn_type(kind) for kind in _all_txn_kinds}
InnerTransactionFieldsetTypes: typing.Final[
    Mapping[constants.TransactionType | None, TransactionRelatedType]
] = {kind: _make_itxn_fieldset_type(kind) for kind in _all_txn_kinds}
InnerTransactionResultTypes: typing.Final[
    Mapping[constants.TransactionType | None, TransactionRelatedType]
] = {kind: _make_itxn_result_type(kind) for kind in _all_txn_kinds}


@attrs.frozen(kw_only=True)
class _CompileTimeType(PyType):
    _wtype_error: str

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        msg = self._wtype_error.format(self=self)
        raise CodeError(msg)

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


@attrs.frozen(kw_only=True)
class IntrinsicEnumType(PyType):
    generic: None = attrs.field(default=None, init=False)
    bases: Sequence[PyType] = attrs.field(
        default=(StrLiteralType,),  # strictly true, but not sure if we want this?
        init=False,
    )
    mro: Sequence[PyType] = attrs.field(default=(StrLiteralType,), init=False)
    members: Mapping[str, str] = attrs.field(converter=immutabledict)

    @property
    def wtype(self) -> wtypes.WType:
        raise CodeError(f"{self} is only valid as a literal argument to an algopy.op function")


def _make_intrinsic_enum_types() -> Sequence[IntrinsicEnumType]:
    from puya.awst_build.intrinsic_data import ENUM_CLASSES

    return [
        _register_builtin(
            IntrinsicEnumType(
                name="".join((constants.ALGOPY_OP_PREFIX, cls_name)),
                members=cls_members,
            )
        )
        for cls_name, cls_members in ENUM_CLASSES.items()
    ]


OpEnumTypes: typing.Final = _make_intrinsic_enum_types()


@attrs.frozen(kw_only=True)
class IntrinsicNamespaceType(PyType):
    generic: None = attrs.field(default=None, init=False)
    bases: Sequence[PyType] = attrs.field(default=(), init=False)
    mro: Sequence[PyType] = attrs.field(default=(), init=False)
    members: Mapping[str, PropertyOpMapping | Sequence[FunctionOpMapping]] = attrs.field(
        converter=immutabledict
    )

    @property
    def wtype(self) -> wtypes.WType:
        raise CodeError(f"{self} is a namespace type only and not usable at runtime")


def _make_intrinsic_namespace_types() -> Sequence[IntrinsicNamespaceType]:
    from puya.awst_build.intrinsic_data import NAMESPACE_CLASSES

    return [
        _register_builtin(
            IntrinsicNamespaceType(
                name="".join((constants.ALGOPY_OP_PREFIX, cls_name)),
                members=cls_members,
            )
        )
        for cls_name, cls_members in NAMESPACE_CLASSES.items()
    ]


OpNamespaceTypes: typing.Final = _make_intrinsic_namespace_types()

StateTotalsType: typing.Final[PyType] = _CompileTimeType(
    name=f"{constants.ALGOPY_PREFIX}_contract.StateTotals",
    wtype_error="{self} is only usable in a class options context",
)

urangeType: typing.Final[PyType] = _CompileTimeType(  # noqa: N816
    name=constants.URANGE,
    wtype_error="{self} is not usable at runtime",
)


def _parameterise_any_compile_time(
    self: _GenericType, args: _TypeArgs, source_location: SourceLocation | None  # noqa: ARG001
) -> PyType:
    arg_names = [arg.name for arg in args]
    name = f"{self.name}[{', '.join(arg_names)}]"
    return _CompileTimeType(name=name, generic=self, wtype_error="{self} is not usable at runtime")


reversedGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name="builtins.reversed",
    parameterise=_parameterise_any_compile_time,
)
uenumerateGenericType: typing.Final[PyType] = _GenericType(  # noqa: N816
    name=constants.UENUMERATE,
    parameterise=_parameterise_any_compile_time,
)


LogicSigType: typing.Final[PyType] = _CompileTimeType(
    name=f"{constants.ALGOPY_PREFIX}_logic_sig.LogicSig",
    wtype_error="{self} is only usable in a static context",
)


@attrs.frozen
class _BaseType(PyType):
    """Type that is only usable as a base type"""

    @typing.override
    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is only usable as a base type")

    def __attrs_post_init__(self) -> None:
        _register_builtin(self)


ContractBaseType: typing.Final[PyType] = _BaseType(name=constants.CONTRACT_BASE)
ARC4ContractBaseType: typing.Final[PyType] = _BaseType(
    name=constants.ARC4_CONTRACT_BASE,
    bases=[ContractBaseType],
    mro=[ContractBaseType],
)
ARC4ClientBaseType: typing.Final[PyType] = _BaseType(name=constants.CLS_ARC4_CLIENT)
ARC4StructBaseType: typing.Final[PyType] = _BaseType(name=constants.CLS_ARC4_STRUCT)
StructBaseType: typing.Final[PyType] = _BaseType(name=constants.STRUCT_BASE)


@typing.final
@attrs.frozen
class PseudoGenericFunctionType(PyType):
    return_type: PyType
    generic: _GenericType[PseudoGenericFunctionType]
    bases: Sequence[PyType] = attrs.field(default=(), init=False)
    mro: Sequence[PyType] = attrs.field(default=(), init=False)

    @property
    def wtype(self) -> typing.Never:
        raise CodeError(f"{self} is not a value")


def _parameterise_pseudo_generic_function_type(
    self: _GenericType[PseudoGenericFunctionType],
    args: _TypeArgs,
    source_location: SourceLocation | None,
) -> PseudoGenericFunctionType:
    try:
        (arg,) = args
    except ValueError:
        raise CodeError(
            f"Expected a single type parameter, got {len(args)} parameters", source_location
        ) from None
    name = f"{self.name}[{arg.name}]"
    return PseudoGenericFunctionType(generic=self, name=name, return_type=arg)


GenericABICallWithReturnType: typing.Final[PyType] = _GenericType(
    name=f"{constants.ARC4_PREFIX}_ABICallWithReturnProtocol",
    parameterise=_parameterise_pseudo_generic_function_type,
)
GenericTemplateVarType: typing.Final[PyType] = _GenericType(
    name=f"{constants.ALGOPY_PREFIX}_template_variables._TemplateVarMethod",
    parameterise=_parameterise_pseudo_generic_function_type,
)


__BASIC_WTYPE_MAP: typing.Final[Mapping[wtypes.WType, PyType]] = {
    wtypes.void_wtype: NoneType,
    wtypes.uint64_wtype: UInt64Type,
    wtypes.bytes_wtype: BytesType,
    wtypes.bool_wtype: BoolType,
    wtypes.account_wtype: AccountType,
    wtypes.biguint_wtype: BigUIntType,
    wtypes.asset_wtype: AssetType,
    wtypes.application_wtype: ApplicationType,
}


def from_basic_wtype(wtype: wtypes.WType) -> PyType:
    """For mapping from basic WTypes _only_.

    These should all be types that are found in the langspec, basically.

    This is only meant for use when there are no other reasonable alternatives.
    """
    try:
        return __BASIC_WTYPE_MAP[wtype]
    except KeyError as ex:
        raise InternalError(f"Unable to map basic WType '{wtype}' back to PyType") from ex
